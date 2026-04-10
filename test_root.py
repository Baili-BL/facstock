from app import app
with app.test_client() as c:
    r = c.get('/')
    print('status', r.status_code)
    print('location', r.headers.get('Location', 'none'))
    print('data[:200]', r.get_data(as_text=True)[:200])
