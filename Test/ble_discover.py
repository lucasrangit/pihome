#!/usr/bin/env python
#
# Discover characteristics of BLE (Bluetooth low energy) devices
#
# Usage: ble_discover.py BLUETOOTH_ADR
#
# Copyright 2014 Thomas Ackermann
# Copyright 2015 Lucas Magasweran
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from collections import OrderedDict
import pexpect
from prettytable import PrettyTable
import re
import sys
import time

attribute_names = {
# GATT Services
  "1800":"access profile",
  "1801":"attribute profile",
# GATT Attribute Types
  "2800":"primary service",
  "2801":"secondary service",
  "2802":"include",
  "2803":"characteristic",
# GATT Characteristic Descriptors
  "2901":"description",
  "2902":"client char config",
# GATT Characteristic Values
  "2a00":"name",
  "2a01":"appearance",
  "2a04":"preferred connection",
  "2a05":"service changed",
  "2a24":"model number",
  "2a25":"serial number",
  "2a26":"firmware revision",
  "2a27":"hardware revision",
  "2a28":"software revision",
  "2a29":"manufacturer",
}

def attribute_name(uuid):
  if uuid.startswith("0x"):
    uuid = uuid[2:]
  if uuid in attribute_names:
    return attribute_names[uuid]
  else:
    return "unknown"

def print_attribute(handle, uuid, description="", value=""):
  s_table.add_row([
      handle,
      uuid,
      description,
      value,
      ])

def read_value(handle):
  tool.sendline("char-read-hnd " + handle)
  tool.expect("descriptor:.*\r\n")
  return tool.after.split()[1:]

def read_string(handle):
  chars = read_value(handle)
  if len(chars) > 0:
    string = ""
    for char in chars:
      idx = int(char, 16)
      if idx > 0:
        string = string + chr(idx)
      else:
        string = string + "\\" + char
    return "'" + string + "'"
  else:
    return "<empty>"

def read_hex(handle):
  chars = read_value(handle)
  if len(chars) > 0:
    string = ""
    for char in chars:
      string = string + char + " "
    return "'" + string[0:-1] + "'"
  else:
    return "<empty>"

def read_uuid(handle):
  chars = read_value(handle)
  if len(chars) > 0:
    string = "0x"
    for char in reversed(chars):
      string += char
    return string
  else:
    return "<empty>"

def read_characteristic(handle):
  chars = read_value(handle)
  if len(chars) == 0:
    return ('', '', '')
  prop = ''.join(chars[0])
  handle = ''.join([chars[2], chars[1]])
# TODO assume 2 byte UUID, can be 2, 4, or 16
  uuid = ''.join([chars[4], chars[3]])
  return (handle, uuid, prop)

def decode_characteristic(handle):
  (value_handle, value_uuid, value_prop) = read_characteristic(handle)
  if len(value_handle) == 0:
    return "<empty>"
  string = "handle: 0x" + value_handle + " uuid: 0x" + value_uuid + " prop: 0x" + value_prop
  return string

def decode_characteristic_value(handle,uuid):
  description = ""
  value = ""
  if   uuid == "2a00":
    description = "name"
    value = read_string(handle)
  elif uuid == "2a01":
    description = "appearance"
    value = read_appearance(handle)
  elif uuid == "2a04":
    description = "preferred connection"
    value = read_conprop(handle)
  elif uuid == "2a05":
    description = "service changed"
  elif uuid == "2a24":
    description = "model number"
    value = read_string(handle)
  elif uuid == "2a25":
    description = "serial number"
    value = read_string(handle)
  elif uuid == "2a26":
    description = "firmware revision"
    value = read_string(handle)
  elif uuid == "2a27":
    description = "hardware revision"
    value = read_string(handle)
  elif uuid == "2a28":
    description = "software revision"
    value = read_string(handle)
  elif uuid == "2a29":
    description = "manufacturer"
    value = read_string(handle)
  else:
    description = "unknown"
    value = read_hex(handle)
  return (description, value)

def property_name(prop):
  val = int(prop, 16)
  prop = prop + " = "
  if val & 0x01:
    prop = prop + "Broadcast "
  if val & 0x02:
    prop = prop + "Read "
  if val & 0x04:
    prop = prop + "WriteRequest "
  if val & 0x08:
    prop = prop + "Write "
  if val & 0x10:
    prop = prop + "Notify "
  if val & 0x20:
    prop = prop + "Indicate "
  if val & 0x40:
    prop = prop + "SignedWrite "
  if val & 0x80:
    prop = prop + "Extended "
  return prop

def read_property(handle):
  tool.sendline("char-read-hnd " + handle)
  tool.expect("descriptor: .*? \r")
  prop = tool.after.split()[1]
  return property_name(prop)

def read_conprop(handle):
  tool.sendline("char-read-hnd " + handle)
  tool.expect("descriptor: .*? \r")
  v = tool.after.split()
  min_int   = str((float.fromhex(v[2] + v[1])) * 1.25)
  max_int   = str((float.fromhex(v[4] + v[3])) * 1.25)
  slave_lat = str((float.fromhex(v[6] + v[5])) * 1.25)
  timeout   = str((float.fromhex(v[8] + v[7])) * 10)
  ret_str  = "min = " + min_int + "ms; max = " + max_int + "ms; "
  ret_str += "lat = " + slave_lat + "ms; timeout = " + timeout + "ms"
  return ret_str

def read_appearance(handle):
  tool.sendline("char-read-hnd " + handle)
  tool.expect("descriptor: .*? \r")
  v = tool.after.split()
  s  = "category: " + str(int(v[2] + v[1],16) & 0x3FF) + " "
  s += "sub-category: " + str(int(v[2] + v[1],16) >> 10)
  return s

def decode_service_value(handle):
  uuid = read_uuid(handle)
  description = 'unknown'
  value = 'unknown'
# GATT Services
  if   uuid == "0x1800":
    description = "access profile"
    value = read_uuid(handle)
  elif uuid == "0x1801":
    description = "attribute profile"
    value = read_uuid(handle)
  return description + " uuid:" + value

def decode_attribute_service(handle, uuid):
  description = ""
  value = ""
# GATT Attribute Types
  if   uuid == "2800":
    description = "primary service"
    value = decode_service_value(handle)
  elif uuid == "2801":
    description = "secondary service"
    value = decode_service_value(handle)
  elif uuid == "2802":
    description = "include"
    value = decode_service_value(handle)
  elif uuid == "2803":
    description = "characteristic"
    value = decode_characteristic(handle)
# GATT Characteristic Descriptors
  elif uuid == "2901":
    description = "description"
    value = read_string(handle)
  return description, value

def discover_services():
  """Return discovered services
  """
  services = OrderedDict()
  start_hnd = 0
  while True:
    if start_hnd != 0:
      tool.sendline('char-desc ' + start_hnd)
    else:
      tool.sendline('char-desc')
    tool.expect('handle')
    tool.expect('[CON]')
    lines = tool.before.split("\r\n")[0:-1]
    lines[0] = 'handle' + lines[0]
    for line in lines:
      tok = line
      tok = re.sub("^.*handle: ", "", tok)
      tok = re.sub("uuid:", "", tok)
      tok = re.sub(",", "", tok)
      (handle, uuid) = tok.split()
      handle = handle.lower()
      uuid = uuid.lower()
      services[handle] = uuid
      start_hnd = handle
    # repeat until less than the maximum packet size is reached
    if len(lines) < 5:
      break
  return services

def scan_characteristics(services):
  characteristics = OrderedDict()
  for handle, uuid in services.items():
    if uuid == '2803':
      (val_handle, val_uuid, val_prop) = read_characteristic(handle)
      characteristics['0x' + val_handle] = (val_uuid, val_prop)
  return characteristics

s_table = PrettyTable([
    "Handle",
    "UUID",
    "Description",
    "Value",
    ])
#s_table.align["Value"] = "l"
s_table.max_width = 20

adr = sys.argv[1]
tool = pexpect.spawn('gatttool -b ' + adr + ' --interactive')
tool.expect('\[LE\]>')

sys.stdout.write("Connecting to '" + adr + "'...\n")
try:
  tool.sendline('connect')
  tool.expect('[CON]')
except:
  sys.stdout.write("Failed to connect. Is device advertising?\n")
time.sleep(1)

sys.stdout.write("Starting service discovery...\n")
services = discover_services()
for handle, uuid in services.items():
  print_attribute(
      handle,
      uuid,
      attribute_name(uuid),
      decode_attribute_service(handle, uuid)[1],
      )
print(s_table)

print("Starting characteristic discovery...")
c_table = PrettyTable([
    "Handle",
    "UUID",
    "Description",
    "Properties",
    "Value",
    ])
c_table.max_width = 20
characteristics = scan_characteristics(services)
for handle,v in characteristics.items():
  uuid = v[0]
  prop = v[1]
  if int(prop,16) & 0x02:
    description, value = decode_characteristic_value(handle, uuid)
  else:
    description = ''
    value = ''
  c_table.add_row([
      handle,
      uuid,
      attribute_name(uuid),
      prop(prop),
      value,
      ])
print(c_table)

