# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from flask import escape
import functions_framework
import redis
import time
import os
import socket

@functions_framework.http
def redis_http(request):
    redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
    time_interval = os.getenv("TIME_INTERVAL", 900)
    time_interval = int(time_interval)
    
    if redis_host == "127.0.0.1":
        print("please correct your redis_host setting!")
        return "please correct your redis_host setting!"

    client = redis.StrictRedis(host=redis_host)
    cursor = '0'

    MESSAGE = "EXIT"

    while cursor != 0:
        try:
            cursor, keys = client.scan(cursor=cursor)
        except Exception as e:
            print("please check your redis connection setting!")
            return "please check your redis connection setting!"
        
        for key in keys:
            result = client.hgetall(key)
            last_access = int(result[b'lastaccess'].decode('utf-8'))
            current_time = int(time.time())
            if current_time - last_access >= time_interval:
                try:
                    host_info = result[b'port'].decode('utf-8').split(":")
                    UDP_IP = host_info[0]
                    UDP_PORT = host_info[1]
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # 
                    loop = 0
                    while loop < 3:
                        sock.sendto(bytes(MESSAGE, "utf-8"), (UDP_IP, int(UDP_PORT)))
                        sock.settimeout(0.5)
                        try:
                            data, address = sock.recvfrom(1024)
                        except socket.timeout:
                            print("timeout to close runtime on {}:{}! please check your firewall config!".format(UDP_IP, UDP_PORT))
                            loop = loop + 1
                            if loop == 3:
                                sock.close()
                            continue
                        if MESSAGE in data.decode('utf-8'):
                            print("successed to close runtime on {}:{}!".format(UDP_IP, UDP_PORT))
                            sock.close()
                            break
                        else:
                            loop = loop + 1
                except Exception as e:
                    print(e)
                    print("failed to close runtime on {}:{}!".format(UDP_IP, UDP_PORT))
                    return "failed to close runtime on {}:{}!".format(UDP_IP, UDP_PORT)
                try:
                    client.delete(key)
                except Exception as e:
                    print(e)
                    print("failed to clear key {}!".format(key))
                    return "failed to clear key {}!".format(key)
    return "success tracking!"
