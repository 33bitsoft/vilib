import argparse

import uvicorn

from app import app, create_admin_user


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="Sunucunun dinleyecegi host (varsayilan: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8086, help="Sunucunun dinleyecegi port (varsayilan: 8086)")
    parser.add_argument("--reload", action="store_true", help="Gelistirme icin otomatik yeniden yukleme")
    subparsers = parser.add_subparsers(dest="command")

    create_admin_parser = subparsers.add_parser("create-admin", help="Admin hesabi olustur")
    create_admin_parser.add_argument("--username", required=True, help="Admin kullanici adi")
    create_admin_parser.add_argument("--password", required=True, help="Admin sifresi")

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    if args.command == "create-admin":
        created = create_admin_user(args.username, args.password)
        if created:
            print("Admin hesabi olusturuldu")
        else:
            print("Bu kullanici adi zaten mevcut")
    else:
        uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)