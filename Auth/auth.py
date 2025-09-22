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
            user_id = decoded_token["oid"]
        except:
            print("Cannot decode token")

    return user_id
