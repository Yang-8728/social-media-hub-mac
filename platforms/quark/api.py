"""
夸克网盘 API 客户端
支持：列目录、上传文件、创建分享链接
"""
import os, json, time, hashlib, base64, xml.etree.ElementTree as ET
import requests
from pathlib import Path
from urllib.parse import unquote

PROJECT_DIR = Path(__file__).resolve().parents[2]
QUARK_CONFIG_FILE = PROJECT_DIR / "config" / "quark.json"

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://pan.quark.cn",
    "Origin": "https://pan.quark.cn",
}

COMMON_PARAMS = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}


def _load_config():
    with open(QUARK_CONFIG_FILE) as f:
        return json.load(f)


def _decode_cookie(cookie_str: str) -> str:
    parts = []
    for part in cookie_str.split("; "):
        if "=" in part:
            k, v = part.split("=", 1)
            parts.append(f"{k}={unquote(v)}")
        else:
            parts.append(part)
    return "; ".join(parts)


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


class QuarkClient:
    BASE = "https://drive-pc.quark.cn"

    def __init__(self):
        cfg = _load_config()
        self.upload_folder = cfg.get("upload_folder", "粉丝定制")
        self.share_expire_days = cfg.get("share_expire_days", 7)
        self.session = requests.Session()
        self.session.headers.update(HEADERS_BASE)
        self.session.headers["Cookie"] = _decode_cookie(cfg["cookie"])

    def _get(self, path, params=None):
        p = {**COMMON_PARAMS, **(params or {})}
        r = self.session.get(f"{self.BASE}{path}", params=p, timeout=30)
        if r.status_code == 401:
            raise PermissionError("夸克Cookie已过期，请运行 python3 scripts/export_quark_cookies.py 更新")
        r.raise_for_status()
        return r.json()

    def _post(self, path, body=None, params=None):
        p = {**COMMON_PARAMS, **(params or {})}
        r = self.session.post(f"{self.BASE}{path}", json=body, params=p, timeout=30)
        if r.status_code == 401:
            raise PermissionError("夸克Cookie已过期，请运行 python3 scripts/export_quark_cookies.py 更新")
        r.raise_for_status()
        return r.json()

    def list_dir(self, pdir_fid="0", page=1, size=100):
        data = self._get("/1/clouddrive/file/sort", params={
            "pdir_fid": pdir_fid,
            "_page": page,
            "_size": size,
            "_fetch_total": 1,
        })
        return (data.get("data") or {}).get("list", [])

    def get_folder_id(self, folder_name: str, parent_fid="0") -> str:
        items = self.list_dir(pdir_fid=parent_fid)
        for item in items:
            if item.get("file_name") == folder_name and item.get("file_type") == 0:
                return item["fid"]
        raise FileNotFoundError(f"夸克网盘中未找到文件夹「{folder_name}」，请先手动创建")

    def mkdir(self, folder_name: str, parent_fid="0") -> str:
        data = self._post("/1/clouddrive/file", body={
            "pdir_fid": parent_fid,
            "file_name": folder_name,
            "dir_init_lock": False,
        })
        return (data.get("data") or {}).get("fid", "")

    def get_or_create_folder(self, folder_name: str, parent_fid="0") -> str:
        try:
            return self.get_folder_id(folder_name, parent_fid)
        except FileNotFoundError:
            return self.mkdir(folder_name, parent_fid)

    def _oss_auth(self, task_id: str, auth_info: str, method: str, mime: str,
                  bucket: str, obj_key: str, upload_id: str,
                  part_number: int = None, callback_b64: str = None,
                  content_md5: str = "") -> tuple:
        time_str = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())

        if part_number is not None:
            resource = f"/{bucket}/{obj_key}?partNumber={part_number}&uploadId={upload_id}"
            oss_headers = (f"x-oss-date:{time_str}\n"
                           "x-oss-user-agent:aliyun-sdk-js/6.6.1 Chrome 98.0.4758.80 on Windows 10 64-bit")
            auth_meta = f"{method}\n\n{mime}\n{time_str}\n{oss_headers}\n{resource}"
        else:
            resource = f"/{bucket}/{obj_key}?uploadId={upload_id}"
            oss_headers = (f"x-oss-callback:{callback_b64}\n"
                           f"x-oss-date:{time_str}\n"
                           "x-oss-user-agent:aliyun-sdk-js/6.6.1 Chrome 98.0.4758.80 on Windows 10 64-bit")
            auth_meta = f"{method}\n{content_md5}\napplication/xml\n{time_str}\n{oss_headers}\n{resource}"

        resp = self._post("/1/clouddrive/file/upload/auth", body={
            "auth_info": auth_info,
            "auth_meta": auth_meta,
            "task_id": task_id,
        })
        return (resp.get("data") or {}).get("auth_key", ""), time_str

    def upload(self, filepath: str, pdir_fid: str) -> tuple:
        filepath = Path(filepath)
        file_size = filepath.stat().st_size
        file_name = filepath.name
        mime = "application/octet-stream"

        with open(filepath, "rb") as f:
            data = f.read()
        pre_hash = _sha1(data[:1024 * 1024])
        file_sha1 = _sha1(data)
        file_md5  = _md5(data)

        pre_resp = self._post("/1/clouddrive/file/upload/pre", body={
            "ccp_hash_update": True,
            "dir_name": "",
            "file_name": file_name,
            "format_type": "zip",
            "pdir_fid": pdir_fid,
            "size": file_size,
            "pre_hash": pre_hash,
        })
        pre_data = pre_resp.get("data") or {}

        if pre_data.get("finish"):
            print(f"[quark] 秒传命中: {file_name}")
            return pre_data.get("fid", ""), pre_data.get("fid_token", "")

        task_id   = pre_data.get("task_id", "")
        upload_url = pre_data.get("upload_url", "")
        obj_key   = pre_data.get("obj_key", "")
        upload_id = pre_data.get("upload_id", "")
        auth_info = pre_data.get("auth_info", "")
        bucket    = pre_data.get("bucket", "")
        callback  = pre_data.get("callback", {})

        if not task_id or not upload_url:
            raise RuntimeError(f"pre-create 失败: {pre_resp}")

        hash_resp = self._post("/1/clouddrive/file/update/hash", body={
            "md5": file_md5,
            "sha1": file_sha1,
            "task_id": task_id,
        })
        hash_data = hash_resp.get("data") or {}
        if hash_data.get("finish"):
            print(f"[quark] 秒传命中（hash）: {file_name}")
            return hash_data.get("fid", ""), hash_data.get("fid_token", "")

        oss_base = f"https://{bucket}.{upload_url.split('://', 1)[-1]}"

        print(f"[quark] 开始上传 {file_name} ({file_size / 1024 / 1024:.1f} MB)...")
        put_auth, put_time = self._oss_auth(task_id, auth_info, "PUT", mime,
                                            bucket, obj_key, upload_id, part_number=1)
        put_resp = requests.put(
            f"{oss_base}/{obj_key}?partNumber=1&uploadId={upload_id}",
            data=data,
            headers={
                "Authorization": put_auth,
                "Content-Type": mime,
                "Referer": "https://pan.quark.cn/",
                "x-oss-date": put_time,
                "x-oss-user-agent": "aliyun-sdk-js/6.6.1 Chrome 98.0.4758.80 on Windows 10 64-bit",
            },
            timeout=600,
        )
        if put_resp.status_code != 200:
            raise RuntimeError(f"PUT 上传失败: {put_resp.status_code} {put_resp.text[:200]}")
        etag = put_resp.headers.get("Etag", "").strip('"')

        xml_body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<CompleteMultipartUpload>"
            f"<Part><PartNumber>1</PartNumber><ETag>{etag}</ETag></Part>"
            "</CompleteMultipartUpload>"
        ).encode()
        xml_md5_b64 = base64.b64encode(hashlib.md5(xml_body).digest()).decode()

        cb = callback if isinstance(callback, dict) else {}
        cb_json = json.dumps({
            "callbackUrl": cb.get("callbackUrl", ""),
            "callbackBody": cb.get("callbackBody", ""),
            "callbackBodyType": "application/x-www-form-urlencoded",
        })
        callback_b64 = base64.b64encode(cb_json.encode()).decode()

        post_auth, post_time = self._oss_auth(
            task_id, auth_info, "POST", "application/xml",
            bucket, obj_key, upload_id,
            callback_b64=callback_b64, content_md5=xml_md5_b64,
        )
        complete_resp = requests.post(
            f"{oss_base}/{obj_key}?uploadId={upload_id}",
            data=xml_body,
            headers={
                "Authorization": post_auth,
                "Content-MD5": xml_md5_b64,
                "Content-Type": "application/xml",
                "Referer": "https://pan.quark.cn/",
                "x-oss-callback": callback_b64,
                "x-oss-date": post_time,
                "x-oss-user-agent": "aliyun-sdk-js/6.6.1 Chrome 98.0.4758.80 on Windows 10 64-bit",
            },
            timeout=60,
        )
        if complete_resp.status_code != 200:
            raise RuntimeError(f"CompleteMultipartUpload 失败: {complete_resp.status_code} {complete_resp.text[:200]}")

        time.sleep(1)
        finish_resp = self._post("/1/clouddrive/file/upload/finish", body={
            "obj_key": obj_key,
            "task_id": task_id,
        })
        finish_data = finish_resp.get("data") or {}
        fid       = finish_data.get("fid", "")
        fid_token = finish_data.get("fid_token", "")

        if not fid:
            raise RuntimeError(f"finish 失败: {finish_resp}")

        print(f"[quark] 上传完成: fid={fid}")
        return fid, fid_token

    def create_share(self, fid: str, fid_token: str, title: str = "", expire_days: int = None) -> str:
        if expire_days is None:
            expire_days = self.share_expire_days

        expire_map = {1: 1, 7: 2, 30: 3, 0: 4}
        expired_type = expire_map.get(expire_days, 2)

        resp = self._post("/1/clouddrive/share", body={
            "fid_list": [fid],
            "fid_token_list": [fid_token],
            "expired_type": expired_type,
            "title": title or "合集分享",
            "url_type": 1,
            "password": "",
        })
        share_data = resp.get("data") or {}
        share_id = share_data.get("share_id", "")
        if not share_id:
            task_resp_data = ((share_data.get("task_resp") or {}).get("data") or {})
            share_id = task_resp_data.get("share_id", "")

        if not share_id:
            raise RuntimeError(f"创建分享失败: {resp}")

        detail = self._get("/1/clouddrive/share/mypage/detail",
                           params={"share_id": share_id})
        items = (detail.get("data") or {}).get("list") or []
        share_url = items[0].get("share_url") if items else None
        if not share_url:
            share_url = f"https://pan.quark.cn/s/{share_id}"

        print(f"[quark] 分享链接: {share_url}")
        return share_url
