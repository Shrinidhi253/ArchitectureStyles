# 1. Register
curl -i -X POST localhost:5000/api/auth/register -H 'Content-Type: application/json' -d '{"username":"nidhi", "password":"dit349"}'

# 2. Log in (prints the token, and saves it in $TOKEN for the next commands)
curl -s -X POST localhost:5000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"nidhi","password":"dit349"}'
TOKEN=$(curl -s -X POST localhost:5000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"nidhi","password":"dit349"}' | sed -E 's/.*"token": ?"([^"]+)".*/\1/')

# 3. Create a device
curl -i -X POST localhost:5000/api/devices -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"name":"temp-1","room":"A101","type":"temperature"}'

# 4. Delete the device (id 1 after --reset)
curl -i -X DELETE localhost:5000/api/devices/1 -H "Authorization: Bearer $TOKEN"

# 5. Request without an Authorization header -> 401
curl -i localhost:5000/api/devices

# 6. Get the audit log
curl localhost:5000/api/audit -H "Authorization: Bearer $TOKEN"