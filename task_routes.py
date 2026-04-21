#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务管理 API 路由（类 Cursor/Claude Code 任务系统）

RESTful API:
  GET    /api/tasks              - 列出任务（支持 ?status=&owner=）
  GET    /api/tasks/:id          - 获取单个任务
  POST   /api/tasks              - 创建任务
  PUT    /api/tasks/:id          - 更新任务
  DELETE /api/tasks/:id          - 删除任务
  GET    /api/tasks/summary      - 统计摘要
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
from database import (
    list_tasks,
    get_task,
    create_task,
    update_task,
    delete_task,
    get_task_summary,
)

task_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')


# ─── 列表 ──────────────────────────────────────────────────────────────────

@task_bp.route('', methods=['GET'])
def api_list_tasks():
    """GET /api/tasks?status=&owner=&limit=100"""
    try:
        status = request.args.get('status')
        owner  = request.args.get('owner')
        limit  = int(request.args.get('limit', 100))
        tasks  = list_tasks(status=status, owner=owner, limit=limit)
        return jsonify({'success': True, 'data': tasks})
    except Exception as e:
        logger.exception('[tasks] list')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── 详情 ──────────────────────────────────────────────────────────────────

@task_bp.route('/<int:task_id>', methods=['GET'])
def api_get_task(task_id):
    """GET /api/tasks/:id"""
    try:
        task = get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        return jsonify({'success': True, 'data': task})
    except Exception as e:
        logger.exception('[tasks] get')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── 创建 ──────────────────────────────────────────────────────────────────

@task_bp.route('', methods=['POST'])
def api_create_task():
    """POST /api/tasks  { subject, description?, owner?, active_form?, priority?, metadata?, blocked_by? }"""
    try:
        body = request.get_json() or {}
        subject    = body.get('subject', '').strip()
        if not subject:
            return jsonify({'success': False, 'error': 'subject 不能为空'}), 400

        task_id = create_task(
            subject     = subject,
            description = body.get('description', ''),
            owner       = body.get('owner'),
            active_form = body.get('active_form'),
            priority    = int(body.get('priority', 0) or 0),
            metadata    = body.get('metadata'),
            blocked_by  = body.get('blocked_by'),
        )
        task = get_task(task_id)
        return jsonify({'success': True, 'data': task}), 201
    except Exception as e:
        logger.exception('[tasks] create')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── 更新 ──────────────────────────────────────────────────────────────────

@task_bp.route('/<int:task_id>', methods=['PUT'])
def api_update_task(task_id):
    """PUT /api/tasks/:id  { subject?, description?, status?, owner?, active_form?, priority?, metadata?, blocked_by? }"""
    try:
        body = request.get_json() or {}

        # 验证 status 值
        valid_statuses = {'pending', 'in_progress', 'completed'}
        if body.get('status') and body['status'] not in valid_statuses:
            return jsonify({'success': False, 'error': f"status 必须是 {valid_statuses} 之一"}), 400

        ok = update_task(
            task_id      = task_id,
            subject      = body.get('subject', '').strip() or None,
            description  = body.get('description'),
            status       = body.get('status'),
            owner        = body.get('owner'),
            active_form  = body.get('active_form'),
            priority     = int(body['priority']) if body.get('priority') is not None else None,
            metadata     = body.get('metadata'),
            blocked_by   = body.get('blocked_by'),
        )
        if not ok:
            return jsonify({'success': False, 'error': '任务不存在或无更新'}), 404

        task = get_task(task_id)
        return jsonify({'success': True, 'data': task})
    except Exception as e:
        logger.exception('[tasks] update')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── 删除 ──────────────────────────────────────────────────────────────────

@task_bp.route('/<int:task_id>', methods=['DELETE'])
def api_delete_task(task_id):
    """DELETE /api/tasks/:id"""
    try:
        ok = delete_task(task_id)
        if not ok:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        return jsonify({'success': True, 'data': {'id': task_id}})
    except Exception as e:
        logger.exception('[tasks] delete')
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── 统计摘要 ────────────────────────────────────────────────────────────────

@task_bp.route('/summary', methods=['GET'])
def api_task_summary():
    """GET /api/tasks/summary"""
    try:
        summary = get_task_summary()
        return jsonify({'success': True, 'data': summary})
    except Exception as e:
        logger.exception('[tasks] summary')
        return jsonify({'success': False, 'error': str(e)}), 500
