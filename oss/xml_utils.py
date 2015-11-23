# -*- coding: utf-8 -*-

"""
oss.xml_utils
~~~~~~~~~~~~~

XML处理相关。

主要包括两类接口：
    - parse_开头的函数：用来解析服务器端返回的XML
    - to_开头的函数：用来生成发往服务器端的XML

"""

import xml.etree.ElementTree as ElementTree

from .models import (SimplifiedObjectInfo,
                     SimplifiedBucketInfo,
                     PartInfo,
                     MultipartUploadInfo,
                     LifecycleRule,
                     LifecycleAction,
                     CorsRule)

from .compat import urlquote, urlunquote, to_unicode


def _find_tag(parent, path):
    child = parent.find(path)
    if child is None:
        raise KeyError("parse xml: " + path + " could not be found under " + parent.tag)
    return child.text or ''


def _find_bool(parent, path):
    text = _find_tag(parent, path)
    if text == 'true':
        return True
    elif text == 'false':
        return False
    else:
        raise ValueError("parse xml: value of " + path + " is not a boolean under " + parent.tag)


def _find_int(parent, path):
    return int(_find_tag(parent, path))


def _find_object(parent, path, url_encoded):
    name = _find_tag(parent, path)
    if url_encoded:
        return urlunquote(name)
    else:
        return name


def _find_all_tags(parent, tag):
    return [node.text or '' for node in parent.findall(tag)]


def _is_url_encoding(root):
    node = root.find('EncodingType')
    if node is not None and node.text == 'url':
        return True
    else:
        return False


def _node_to_string(root):
    return ElementTree.tostring(root, encoding='utf-8')


def _add_node_list(parent, tag, entries):
    for e in entries:
        _add_text_child(parent, tag, e)


def _add_text_child(parent, tag, text):
    ElementTree.SubElement(parent, tag).text = to_unicode(text)


def _make_encoder(encoding_type):
    if encoding_type == 'url':
        return urlquote
    else:
        return lambda x: x


def parse_list_objects(result, body):
    root = ElementTree.fromstring(body)
    url_encoded = _is_url_encoding(root)

    result.is_truncated = _find_bool(root, 'IsTruncated')
    if result.is_truncated:
        result.next_marker = _find_object(root, 'NextMarker', url_encoded)

    for contents_node in root.findall('Contents'):
        result.object_list.append(SimplifiedObjectInfo(
            _find_object(contents_node, 'Key', url_encoded),
            _find_tag(contents_node, 'LastModified'),
            _find_tag(contents_node, 'ETag').strip('"'),
            _find_tag(contents_node, 'Type'),
            int(_find_tag(contents_node, 'Size')),
            _find_tag(contents_node, 'StorageClass')
        ))

    for prefix_node in root.findall('CommonPrefixes'):
        result.prefix_list.append(_find_object(prefix_node, 'Prefix', url_encoded))

    return result


def parse_list_buckets(result, body):
    root = ElementTree.fromstring(body)

    if root.find('IsTruncated') is None:
        result.is_truncated = False
    else:
        result.is_truncated = _find_bool(root, 'IsTruncated')

    if result.is_truncated:
        result.next_marker = _find_tag(root, 'NextMarker')

    for bucket_node in root.findall('Buckets/Bucket'):
        result.buckets.append(SimplifiedBucketInfo(
            _find_tag(bucket_node, 'Name'),
            _find_tag(bucket_node, 'Location'),
            _find_tag(bucket_node, 'CreationDate')
        ))


def parse_init_multipart_upload(result, body):
    root = ElementTree.fromstring(body)
    result.upload_id = _find_tag(root, 'UploadId')

    return result


def parse_list_multipart_uploads(result, body):
    root = ElementTree.fromstring(body)

    url_encoded = _is_url_encoding(root)

    result.is_truncated = _find_bool(root, 'IsTruncated')
    result.next_key_marker = _find_object(root, 'NextKeyMarker', url_encoded)
    result.next_upload_id_marker = _find_tag(root, 'NextUploadIdMarker')

    for upload_node in root.findall('Upload'):
        result.upload_list.append(MultipartUploadInfo(
            _find_object(upload_node, 'Key', url_encoded),
            _find_tag(upload_node, 'UploadId'),
            _find_tag(upload_node, 'Initiated')
        ))

    for prefix_node in root.findall('CommonPrefixes'):
        result.prefix_list.append(_find_object(prefix_node, 'Prefix', url_encoded))

    return result


def parse_list_parts(result, body):
    root = ElementTree.fromstring(body)

    result.is_truncated = _find_bool(root, 'IsTruncated')
    result.next_marker = _find_tag(root, 'NextPartNumberMarker')
    for part_node in root.findall('Part'):
        result.parts.append(PartInfo(
            _find_int(part_node, 'PartNumber'),
            _find_tag(part_node, 'ETag').strip('"'),
            _find_int(part_node, 'Size'),

        ))

    return result


def parse_batch_delete_objects(result, body):
    if not body:
        return result

    root = ElementTree.fromstring(body)
    url_encoded = _is_url_encoding(root)

    for deleted_node in root.findall('Deleted'):
        result.object_list.append(_find_object(deleted_node, 'Key', url_encoded))

    return result


def parse_get_bucket_acl(result, body):
    root = ElementTree.fromstring(body)
    result.acl = _find_tag(root, 'AccessControlList/Grant')

    return result

parse_get_object_acl = parse_get_bucket_acl


def parse_get_bucket_location(result, body):
    result.location = ElementTree.fromstring(body).text
    return result


def parse_get_bucket_logging(result, body):
    root = ElementTree.fromstring(body)

    if root.find('LoggingEnabled/TargetBucket') is not None:
        result.target_bucket = root.find('LoggingEnabled/TargetBucket').text

    if root.find('LoggingEnabled/TargetPrefix') is not None:
        result.target_prefix = root.find('LoggingEnabled/TargetPrefix').text

    return result


def parse_get_bucket_referer(result, body):
    root = ElementTree.fromstring(body)

    result.allow_empty_referer = _find_bool(root, 'AllowEmptyReferer')
    for referer in root.findall('RefererList/Referer'):
        result.referers.append(referer.text)

    return result


def parse_get_bucket_websiste(result, body):
    root = ElementTree.fromstring(body)

    result.index_file = root.find('IndexDocument/Suffix').text
    result.error_file = root.find('ErrorDocument/Key').text

    return result


def parse_lifecycle_actions(rule_node):
    actions = []

    for node in rule_node.findall('*'):
        if node.tag in ('ID', 'Prefix', 'Status'):
            continue

        time_node = node.findall('*')[0]
        actions.append(LifecycleAction(node.tag, time_node.tag, time_node.text))

    return actions


def parse_get_bucket_lifecycle(result, body):
    root = ElementTree.fromstring(body)

    for rule_node in root.findall('Rule'):
        rule = LifecycleRule(
            _find_tag(rule_node, 'ID'),
            _find_tag(rule_node, 'Prefix'),
            _find_tag(rule_node, 'Status'),
            parse_lifecycle_actions(rule_node))
        result.rules.append(rule)

    return result


def parse_get_bucket_cors(result, body):
    root = ElementTree.fromstring(body)

    for rule_node in root.findall('CORSRule'):
        rule = CorsRule()
        rule.allowed_origins = _find_all_tags(rule_node, 'AllowedOrigin')
        rule.allowed_methods = _find_all_tags(rule_node, 'AllowedMethod')
        rule.allowed_headers = _find_all_tags(rule_node, 'AllowedHeader')
        rule.expose_headers = _find_all_tags(rule_node, 'ExposeHeader')

        max_age_node = rule_node.find('MaxAgeSeconds')
        if max_age_node is not None:
            rule.max_age_seconds = int(max_age_node.text)

        result.rules.append(rule)

    return result


def to_complete_upload_request(parts):
    root = ElementTree.Element('CompleteMultipartUpload')
    for p in parts:
        part_node = ElementTree.SubElement(root, "Part")
        _add_text_child(part_node, 'PartNumber', str(p.part_number))
        _add_text_child(part_node, 'ETag', '"{0}"'.format(p.etag))

    return _node_to_string(root)


def to_batch_delete_objects_request(objects, quiet):
    root_node = ElementTree.Element('Delete')

    _add_text_child(root_node, 'Quiet', str(quiet).lower())

    for object_name in objects:
        object_node = ElementTree.SubElement(root_node, 'Object')
        _add_text_child(object_node, 'Key', object_name)

    return _node_to_string(root_node)


def to_put_bucket_logging(bucket_logging):
    root = ElementTree.Element('BucketLoggingStatus')

    if bucket_logging.target_bucket:
        logging_node = ElementTree.SubElement(root, 'LoggingEnabled')
        _add_text_child(logging_node, 'TargetBucket', bucket_logging.target_bucket)
        _add_text_child(logging_node, 'TargetPrefix', bucket_logging.target_prefix)

    return _node_to_string(root)


def to_put_bucket_referer(bucket_referer):
    root = ElementTree.Element('RefererConfiguration')

    _add_text_child(root, 'AllowEmptyReferer', str(bucket_referer.allow_empty_referer).lower())
    list_node = ElementTree.SubElement(root, 'RefererList')

    for r in bucket_referer.referers:
        _add_text_child(list_node, 'Referer', r)

    return _node_to_string(root)


def to_put_bucket_website(bucket_websiste):
    root = ElementTree.Element('WebsiteConfiguration')

    index_node = ElementTree.SubElement(root, 'IndexDocument')
    _add_text_child(index_node, 'Suffix', bucket_websiste.index_file)

    error_node = ElementTree.SubElement(root, 'ErrorDocument')
    _add_text_child(error_node, 'Key', bucket_websiste.error_file)

    return _node_to_string(root)


def to_put_bucket_lifecycle(bucket_lifecycle):
    root = ElementTree.Element('LifecycleConfiguration')

    for rule in bucket_lifecycle.rules:
        rule_node = ElementTree.SubElement(root, 'Rule')
        _add_text_child(rule_node, 'ID', rule.id)
        _add_text_child(rule_node, 'Prefix', rule.prefix)
        _add_text_child(rule_node, 'Status', rule.status)

        for action in rule.actions:
            action_node = ElementTree.SubElement(rule_node, action.action)
            _add_text_child(action_node, action.time_spec, action.time_value)

    return _node_to_string(root)


def to_put_bucket_cors(bucket_cors):
    root = ElementTree.Element('CORSConfiguration')

    for rule in bucket_cors.rules:
        rule_node = ElementTree.SubElement(root, 'CORSRule')
        _add_node_list(rule_node, 'AllowedOrigin', rule.allowed_origins)
        _add_node_list(rule_node, 'AllowedMethod', rule.allowed_methods)
        _add_node_list(rule_node, 'AllowedHeader', rule.allowed_headers)
        _add_node_list(rule_node, 'ExposeHeader', rule.expose_headers)

        if rule.max_age_seconds is not None:
            _add_text_child(rule_node, 'MaxAgeSeconds', str(rule.max_age_seconds))

    return _node_to_string(root)