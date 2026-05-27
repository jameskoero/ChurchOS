# hardened_auth_patch.py
# Merge /refresh and /logout into your auth blueprint.
# James Koero · 2026
from flask import jsonify
from flask_jwt_extended import (
    jwt_required, get_jwt, get_jwt_identity,
    create_access_token, create_refresh_token,
)

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    old_jti  = get_jwt()["jti"]
    identity = get_jwt_identity()
    claims   = {k: v for k, v in get_jwt().items()
                if k in ("church_id", "role")}
    TokenBlocklist.revoke(old_jti, token_type="refresh")
    return jsonify(
        access_token=create_access_token(
            identity=identity, additional_claims=claims),
        refresh_token=create_refresh_token(
            identity=identity, additional_claims=claims),
    ), 200

@auth_bp.route("/logout", methods=["DELETE"])
@jwt_required(verify_type=False)
def logout():
    TokenBlocklist.revoke(
        get_jwt()["jti"], token_type=get_jwt()["type"])
    return jsonify(message="Logged out"), 200
