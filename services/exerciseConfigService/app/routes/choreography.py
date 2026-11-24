from flask import Blueprint, request, jsonify

from app.choreography import (
    choreography_exists,
    create_choreography,
    get_choreography,
    replace_choreography,
    delete_choreography,
    list_choreographies,
    choreographies_using,
    validate_choreography,
)

choreography_bp = Blueprint("choreography", __name__, url_prefix="/choreography")


# ---------------------------------------------------------------------------
# GET /choreography/list
# ---------------------------------------------------------------------------
@choreography_bp.route("/list", methods=["GET"])
def list_all():
    return jsonify(list_choreographies()), 200


# ---------------------------------------------------------------------------
# POST /choreography/create
# Body (JSON): the whole choreography document (states, transitions, initial_state)
# ---------------------------------------------------------------------------
@choreography_bp.route("/create", methods=["POST"])
def create():
    doc = request.get_json(silent=True)
    if doc is None:
        return jsonify({"error": "JSON body required"}), 400

    errors = validate_choreography(doc)
    if errors:
        return jsonify({"error": "invalid choreography", "errors": errors}), 400

    created = create_choreography(doc)
    return jsonify(created), 201


# ---------------------------------------------------------------------------
# GET /choreography/<id>
# ---------------------------------------------------------------------------
@choreography_bp.route("/<choreography_id>", methods=["GET"])
def get(choreography_id):
    if not choreography_exists(choreography_id):
        return jsonify({"error": f"Choreography '{choreography_id}' not found"}), 404
    return jsonify(get_choreography(choreography_id)), 200


# ---------------------------------------------------------------------------
# PUT /choreography/<id>
# Body (JSON): the whole choreography document, sent by the editor
# ---------------------------------------------------------------------------
@choreography_bp.route("/<choreography_id>", methods=["PUT"])
def put(choreography_id):
    if not choreography_exists(choreography_id):
        return jsonify({"error": f"Choreography '{choreography_id}' not found"}), 404

    doc = request.get_json(silent=True)
    if doc is None:
        return jsonify({"error": "JSON body required"}), 400

    errors = validate_choreography(doc)
    if errors:
        return jsonify({"error": "invalid choreography", "errors": errors}), 400

    updated = replace_choreography(choreography_id, doc)
    return jsonify(updated), 200


# ---------------------------------------------------------------------------
# DELETE /choreography/<id>
# Deletes the graph only; the referenced exercises stay untouched.
# ---------------------------------------------------------------------------
@choreography_bp.route("/<choreography_id>", methods=["DELETE"])
def delete(choreography_id):
    if not choreography_exists(choreography_id):
        return jsonify({"error": f"Choreography '{choreography_id}' not found"}), 404
    delete_choreography(choreography_id)
    return jsonify({"deleted": choreography_id}), 200
