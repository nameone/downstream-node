#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pickle

from flask import jsonify, request

from .startup import app
from .lib import (create_token, get_chunk_contract,
                  verify_proof,  update_contract,
                  lookup_contract)
from .models import Contract
from datetime import datetime


@app.route('/')
def api_index():
    return jsonify(msg='ok')


@app.route('/api/downstream/status')
def api_downstream_status():
    try:
        contracts = Contract.query.filter(Contract.expiration
                                          > datetime.utcnow()).all()

        farmers = list(
            map(lambda x: {'id': x.id,
                           'uptime': int((datetime.utcnow()-x.start).
                                         total_seconds())},
                contracts))

        return jsonify(farmers=farmers)
    except Exception as ex:
        resp = jsonify(status='error',
                       message=str(ex))
        resp.status_code = 500
        return resp


@app.route('/api/downstream/new/<sjcx_address>')
def api_downstream_new_token(sjcx_address):
    # generate a new token
    try:
        db_token = create_token(sjcx_address)
        beat = pickle.loads(db_token.heartbeat)
        pub_beat = beat.get_public()
        return jsonify(token=db_token.token,
                       type=type(beat).__name__,
                       heartbeat=pub_beat.todict())
    except Exception as ex:
        resp = jsonify(status='error',
                       message=str(ex))
        resp.status_code = 500
        return resp


@app.route('/api/downstream/chunk/<token>')
def api_downstream_chunk_contract(token):
    try:
        db_contract = get_chunk_contract(token)

        with open(db_contract.tag_path, 'rb') as f:
            tag = pickle.loads(f.read())
        chal = pickle.loads(db_contract.challenge)

        # now since we are prototyping, we can delete the tag and file
        os.remove(db_contract.file.path)
        os.remove(db_contract.tag_path)

        return jsonify(seed=db_contract.seed,
                       size=db_contract.size,
                       file_hash=db_contract.file.hash,
                       challenge=chal.todict(),
                       tag=tag.todict(),
                       expiration=db_contract.expiration.isoformat())

    except Exception as ex:
        resp = jsonify(status='error',
                       message=str(ex))
        resp.status_code = 500
        return resp


@app.route('/api/downstream/challenge/<token>/<file_hash>')
def api_downstream_chunk_contract_status(token, file_hash):
    """For prototyping, this will generate a new challenge
    """
    try:
        db_contract = update_contract(token, file_hash)

        return jsonify(challenge=pickle.loads(db_contract.challenge).todict(),
                       expiration=db_contract.expiration.isoformat())

    except Exception as ex:
        print(ex)
        resp = jsonify(status='error',
                       message=str(ex))
        resp.status_code = 500
        return resp


@app.route('/api/downstream/answer/<token>/<file_hash>', methods=['POST'])
def api_downstream_challenge_answer(token, file_hash):
    try:
        d = request.get_json(silent=True)

        if (dict is False or not isinstance(d, dict) or 'proof' not in d):
            raise RuntimeError('Posted data must be an JSON encoded \
proof object: {"proof":"...proof object..."}')

        db_contract = lookup_contract(token, file_hash)

        beat = pickle.loads(db_contract.token.heartbeat)

        try:
            proof = beat.proof_type().fromdict(d['proof'])
        except:
            raise RuntimeError('Proof corrupted.')

        if (not verify_proof(token, file_hash, proof)):
            raise RuntimeError('Invalid proof, or proof expired.')

        return jsonify(status='ok')

    except Exception as ex:
        print(ex)
        resp = jsonify(status='error',
                       message=str(ex))
        resp.status_code = 500
        return resp
