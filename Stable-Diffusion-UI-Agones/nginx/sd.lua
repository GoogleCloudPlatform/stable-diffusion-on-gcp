--  Copyright 2023 Google LLC
-- 
--  Licensed under the Apache License, Version 2.0 (the "License");
--  you may not use this file except in compliance with the License.
--  You may obtain a copy of the License at
-- 
--      http://www.apache.org/licenses/LICENSE-2.0
-- 
--  Unless required by applicable law or agreed to in writing, software
--  distributed under the License is distributed on an "AS IS" BASIS,
--  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
--  See the License for the specific language governing permissions and
--  limitations under the License.
local headers = ngx.req.get_headers()
local key = headers["x-goog-authenticated-user-email"]
-- print(key)

if not key then
    if headers["user-agent"] == "GoogleHC/1.0" then
        ngx.log(ngx.INFO, "health check success!")
        ngx.say("health check success!")
        return ngx.exit(200)
    end
    ngx.log(ngx.ERR, "no iap user identity found")
    ngx.status = 400
    ngx.say("fail to fetch user identity!")
    return ngx.exit(400)
end

local redis = require "resty.redis"
local red = redis:new()

red:set_timeout(1000) -- 1 second
local ok, err = red:connect("${REDIS_HOST}", 6379)
if not ok then
    ngx.log(ngx.ERR, "failed to connect to redis: ", err)
    ngx.status = 500
    ngx.say("failed to connect to redis!")
    return ngx.exit(500)
end

local secs = ngx.time()

local lookup_res, err = red:hget(key, "target")
print(lookup_res)

if lookup_res == ngx.null then                
    local http = require "resty.http"
    local httpc = http.new()
    ngx.log(ngx.INFO, [[{"namespace": "default", "metadata": {"labels": {"user": "]] .. key .. [["}}}]])
    local sub_key = string.gsub(key, ":", ".")
    local final_uid = string.gsub(sub_key, "@", ".")
    local res, err = httpc:request_uri(
        "http://agones-allocator.agones-system.svc.cluster.local:443/gameserverallocation",
            {
            method = "POST",
            body = [[{"namespace": "default", "metadata": {"labels": {"user": "]] .. final_uid .. [["}}}]],
          }
    )

    local cjson = require "cjson"
    local resp_data = cjson.decode(res.body)
    local host = resp_data["address"]
    if host == nil then
        ngx.header.content_type = "text/html"
        ngx.say([[<h1>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Too many users, Please try later! We are cooking for you!</h1><img src="images/coffee-clock.jpg" alt="Take a cup of coffea" />]])
        return
    end

    local sd_port = resp_data["ports"][2]["port"]
    local gs_port = resp_data["ports"][1]["port"]
    
    if string.match(host, "internal") ~= nil then
        local resolver = require "resty.dns.resolver"
        local dns = "169.254.169.254"

        local r, err = resolver:new{
            nameservers = {dns},
            retrans = 3,  -- 3 retransmissions on receive timeout
            timeout = 1000,  -- 1 sec
        }

        if not r then
            ngx.log(ngx.ERR, "failed to instantiate the resolver!")
            ngx.status = 400
            ngx.say("failed to instantiate the resolver!")
            return ngx.exit(400)
        end

        local answers, err = r:query(host)
        if not answers then
            ngx.log(ngx.ERR, "failed to query the DNS server!")
            ngx.status = 400
            ngx.say("failed to query the DNS server!")
            return ngx.exit(400)
        end

        if answers.errcode then
            ngx.log(ngx.ERR, "dns server returned error code!")
            ngx.status = 400
            ngx.say("dns server returned error code!")
            return ngx.exit(400)
        end

        for i, ans in ipairs(answers) do
            if ans.address then
                ngx.log(ngx.INFO, ans.address)
                host = ans.address
            end
        end
    end

    ngx.var.target = host .. ":" .. sd_port
    ngx.log(ngx.INFO, "set redis ", ngx.var.target)
--     print("set redis ", ngx.var.target)

    ok, err = red:hset(key, "target", ngx.var.target, "port", host .. ":" .. gs_port, "lastaccess", secs)
    if not ok then
--         print("fail to set redis key")
        ngx.log(ngx.ERR, "failed to hset: ", err)
        ngx.say("failed to hset: ", err)
        return
    end
else
    ngx.var.target = lookup_res
    ok, err = red:hset(key, "lastaccess", secs)
    if not ok then
--         print("fail to set redis key")
        ngx.log(ngx.ERR, "failed to hset: ", err)
        ngx.say("failed to hset: ", err)
        return
    end
end
