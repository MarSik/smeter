#!/usr/bin/python -u

import sys, math, binascii, struct
from bitarray import bitarray
from crcmod import Crc
from collections import defaultdict
from hamm import hamming
from time import gmtime, strftime

# Resources:
# www.st.com/resource/en/application_note/dm00233038.pdf
# http://oms-group.org/fileadmin/pdf/OMS-Spec_Vol2_Primary_v301.pdf
# https://github.com/mjung85/iotsys/blob/master/wiki/MBusConnector.md 

# poly: x16+x13+x12+x11+x10+x8+x6+x5+x2+1
poly=(1<<16)+(1<<13)+(1<<12)+(1<<11)+(1<<10)+(1<<8)+(1<<6)+(1<<5)+(1<<2)+1
CRC16 = Crc(poly, initCrc=0xffff, rev=False, xorOut=0xffff)

CVALS = {
    0x44: "SND-NR",
    0x47: "ACC-NR",
    0x08: "RSP-UD",
    0x18: "RSP-UD",
    0x28: "RSP-UD",
    0x38: "RSP-UD"
}

CIVALS = {
    0x72: "RfD-12-Mb",
}

def crc(data):
    crc16 = CRC16.copy()
    crc16.update(data)
    return crc16.digest()

def todate(d):
    d=[ord(c) for c in d]
    return '%04d-%02d-%02d' % (
        (d[1] >> 5) + 2014,
        ((d[1]>>1) & 0xf),
        ((d[1] & 1) << 4) | (d[0] >> 4))

def decode2Bto3ch(vendor):
    manuf = []
    for i in xrange(3):
        manuf.append(chr(0x40 + (vendor & 0x1f)))
        vendor >>= 5
    return ''.join(reversed(manuf))

def dump(decoded):
    if len(decoded) < 24:
        return

    vendor = struct.unpack("<H", decoded[2:4])[0]
    manuf = decode2Bto3ch(vendor)

    addr = format(ord(pkt[4]),"02x")+format(ord(pkt[5]),"02x")
    size = ord(decoded[0])

    print strftime("%d %b %Y %H:%M:%S", gmtime()),
    print "<L %d>" % size,
    print "<C %s>" %  CVALS.get(ord(decoded[1]), binascii.hexlify(decoded[1])),
    print "<M %s>" % manuf,
    print "<addr %s>" % hexdump(decoded[4:10]),
    print "<crc %s %s>" % (hexdump(decoded[10:12]), "ok" if crc(decoded[:10]) == decoded[10:12] else "F!"), # CRC
    decoded = decoded[12:]
    size -= 9 # CRC and len field do not count
    ci = None

    appdata = ""

    while decoded:
      block_size = min(16, size)
      block_start = 0
      size -= block_size
      block = decoded[:block_size + 2] # 16 + 2 for CRC
      decoded = decoded[block_size + 2:]
      crc_real = crc(block[:block_size])

      print "| [L=%d]" % block_size,
      
      if ci is None:
          ci = CIVALS.get(ord(block[0]), hexdump(block[0]))
          print "<CI %s>" % ci,
          block_start = 1

      # print hexdump(block[block_start:block_size]),
      print "<crc %s %s>" % (hexdump(block[block_size:]), "ok" if crc_real == block[block_size:] else "F!"), # CRC
      appdata += block[:block_size]

    print "=",
    print hexdump(appdata[0:6]),
    print "<Date %s>" % todate(appdata[6:8]),
    print hexdump(appdata[8:]),
    print

def split_by_n( seq, n ):
    """A generator to divide a sequence into chunks of n units.
       src: http://stackoverflow.com/questions/9475241/split-python-string-every-nth-character"""
    while seq:
        yield seq[:n]
        seq = seq[n:]

def hexdump(a):
    return ' '.join(split_by_n(binascii.hexlify(a),4))

if __name__ == '__main__':
    for line in iter(sys.stdin.readline, ""):
      line = ''.join(line.split())
      if len(line) % 2: # Invalid packet, odd number of hex chars
          continue
      try:
        pkt = binascii.unhexlify(line)
      except TypeError:
        continue
      dump(pkt)

