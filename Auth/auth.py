from fastapi import Request
import jwt


def authorize_user(request: Request):

    authorization_cookie = request.cookies.get("authorization")
    user_id = None

    # Get user Id for his context history
    if authorization_cookie:
        try:
            decoded_token = jwt.decode(
                authorization_cookie, options={"verify_signature": False}
            )
            print(decoded_token)
            user_id = decoded_token["user_id"]
        except:
            print("Cannot decode token")

    if not user_id:
        # ui.navigate.to("http://localhost:33001/")
        return "d1822e48-2f4b-405c-a429-e0c0a37dc8a6"

    return user_id
