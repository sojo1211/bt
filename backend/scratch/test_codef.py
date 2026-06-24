import asyncio, httpx, base64, urllib.parse, json

CODEF_CLIENT_ID = 'a1205988-68a6-49fc-9d7c-54cdbce3622c'
CODEF_CLIENT_SECRET = 'ad5121e2-2fcc-4788-89e7-5b8a31305998'
CODEF_TOKEN_URL = 'https://oauth.codef.io/oauth/token'

async def test():
    credentials = base64.b64encode(f'{CODEF_CLIENT_ID}:{CODEF_CLIENT_SECRET}'.encode()).decode()
    async with httpx.AsyncClient() as client:
        res = await client.post(
            CODEF_TOKEN_URL,
            headers={'Authorization': f'Basic {credentials}', 'Content-Type': 'application/x-www-form-urlencoded'},
            data={'grant_type': 'client_credentials', 'scope': 'read'}, timeout=10.0
        )
        token = res.json()['access_token']
        
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        endpoints = [
            'https://development.codef.io/v1/kr/public/ef/driver-license/status',
            'https://development.codef.io/v1/kr/public/ef/driver-license/KoRoad-status',
            'https://development.codef.io/v1/kr/public/pa/driver-license/status'
        ]
        orgs = ['0001', '0002', '0003', '0004']
        
        for ep in endpoints:
            for org in orgs:
                payload = {'organization': org, 'birthDate': '20020218', 'licenseNo': '112103845780', 'userName': '박찬호'}
                try:
                    r = await client.post(ep, headers=headers, json=payload, timeout=20.0)
                    text = urllib.parse.unquote(r.text)
                    try:
                        j = json.loads(text)
                        code = j.get('result', {}).get('code')
                        msg = j.get('result', {}).get('message')
                    except:
                        code = r.status_code
                        msg = text
                    short_ep = ep.split('/')[-2] + '/' + ep.split('/')[-1]
                    print(f'EP: {short_ep}, ORG: {org} => {code}: {msg}')
                except Exception as e:
                    short_ep = ep.split('/')[-2] + '/' + ep.split('/')[-1]
                    print(f'EP: {short_ep}, ORG: {org} => ERROR: {e}')

asyncio.run(test())
