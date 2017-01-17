#!/usr/bin/python -u
# encoding: utf-8

import sys, math, binascii, struct
from crcmod import Crc
from time import gmtime, strftime
from datetime import datetime, timedelta

# Resources:
# http://www.rtl-sdr.com/decoding-public-utility-meters-with-an-rtl-sdr/
# www.st.com/resource/en/application_note/dm00233038.pdf
# http://oms-group.org/fileadmin/pdf/OMS-Spec_Vol2_Primary_v301.pdf
# https://github.com/mjung85/iotsys/blob/master/wiki/MBusConnector.md 
# https://forum.fhem.de/index.php/topic,42232.html
# https://github.com/mhop/fhem-mirror/blob/master/fhem/FHEM/32_TechemHKV.pm

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
    0x72: "RfD-12-Mb", # Standard wMbus response
    0xA0: "TechemBin",
    0xA1: "TechemBcd" # Probably
}

DEVVALS = {
    0x62: "HotW",
    0x72: "ColW",
    0x80: "Heat", # Heating meter
}

def crc(data):
    crc16 = CRC16.copy()
    crc16.update(data)
    return crc16.digest()

def nextdate(last_date, month, day):
    """
    Compute a new datetime object representing the closest
    month and day in future (starting with the last_date)
    """
    next_date = last_date.replace(month = month, day = day)
    if (next_date < last_date):
	next_date = next_date.replace(year = next_date.year)
    return next_date

def todate(last_date, d):
    d=struct.unpack('<H', d)[0]
    return nextdate(last_date,
        month = max(1, (d >> 9) & 0x0f),
        day = max(1, (d >> 4) & 0x1f))

def tolastdate(d):
    d=struct.unpack('<H', d)[0]
    return datetime(
        year = 2000 + ((d >> 9) & 0x3f),
        month = max(1, (d >> 5) & 0x0f), # Make sure the parsing does
        day = max(1, d & 0x1f))          # not fail on month / day values


def decodeid(d):
    assert len(d) == 4
    return hexdump(d[::-1])

def decode2Bto3ch(vendor):
    """
    Decode the vendor string. Converts 2 bytes into
    three characters.
    """
    manuf = []
    for i in xrange(3):
        manuf.append(chr(0x40 + (vendor & 0x1f)))
        vendor >>= 5
    return ''.join(reversed(manuf))

def dump(decoded):
    if len(decoded) < 24:
        return

    manufraw = struct.unpack("<H", decoded[2:4])[0]
    manuf = decode2Bto3ch(manufraw)

    size = ord(decoded[0])
    command = ord(decoded[1])
    addr = decodeid(decoded[4:8])
    version = ord(decoded[8])
    device = ord(decoded[9])

    print strftime("%d %b %Y %H:%M:%S", gmtime()),
    print "<L %d>" % size,
    print "<C %s>" %  CVALS.get(command, hex(command)),
    print "<M %s>" % manuf,
    print "<addr %s>" % addr,
    print "<ver %s>" % hex(version),
    print "<dev % 4s>" % DEVVALS.get(device, hex(device)),
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
      ci = None

      print "| [L=%02d]" % block_size,
      
      if ci is None:
          ci = ord(block[0])
          block_start = 1

      print "<crc %s %s>" % (hexdump(block[block_size:]), "ok" if crc_real == block[block_size:] else "F!"), # CRC
      appdata += block[block_start:block_size]

    last_date = tolastdate(appdata[1:3])
    last_reading = struct.unpack('<H', appdata[3:5])[0]
    status = ord(appdata[0])
    daily_date = todate(last_date, appdata[5:7])
    daily_reading = struct.unpack('<H', appdata[7:9])[0]
    t1 = struct.unpack('<H', appdata[9:11])[0]/100.0
    t2 = struct.unpack('<H', appdata[11:13])[0]/100.0

    print "=",
    print "<CI %s>" % CIVALS.get(ci, hex(ci)),
    print "<S %s>" % bin(status),
    print "<Last Date %s>" % last_date.strftime("%Y-%m-%d"),
    print "<Last %d>" % last_reading,
    print "<Date %s>" % daily_date.strftime("%Y-%m-%d"),
    print "<Cur %d>" % daily_reading,
    print "<T1 %2.2f°C>" % t1,
    print "<T2 %2.2f°C>" % t2,
    print hexdump(appdata[13:]),
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

