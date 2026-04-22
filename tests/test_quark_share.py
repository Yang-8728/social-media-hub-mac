"""
pipelines/quark_share.py 的 mock 测试。
覆盖：IG下载、zip打包、B站回复、run() 主流程。
"""
import json
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest

import pipelines.quark_share as qs


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_post(shortcode, is_video=True, video_url="http://example.com/v.mp4"):
    p = MagicMock()
    p.is_video = is_video
    p.shortcode = shortcode
    p.video_url = video_url
    return p


def _make_quark_client(share_url="https://pan.quark.cn/s/test123"):
    c = MagicMock()
    c.upload_folder = "粉丝定制"
    c.get_or_create_folder.return_value = "folder_fid"
    c.upload.return_value = ("fid123", "fid_token_abc")
    c.create_share.return_value = share_url
    return c


# ── _download_ig_profile ──────────────────────────────────────────────────────

class TestDownloadIgProfile:

    def test_raises_if_no_session_file(self, tmp_path):
        with patch("os.path.exists", return_value=False):
            with pytest.raises(RuntimeError, match="session 文件不存在"):
                qs._download_ig_profile("testuser")

    def test_reuses_cached_files_without_redownloading(self, tmp_path):
        """已下载的文件直接复用，不触发 requests.get"""
        out_dir = tmp_path / "testuser"
        out_dir.mkdir()
        cached = out_dir / "ABC123.mp4"
        cached.write_bytes(b"x" * 500)

        mock_profile = MagicMock()
        mock_profile.get_posts.return_value = [_make_post("ABC123")]

        with patch("os.path.exists", return_value=True), \
             patch("instaloader.Instaloader"), \
             patch("instaloader.Profile.from_username", return_value=mock_profile), \
             patch.object(qs, "DOWNLOAD_DIR", tmp_path), \
             patch.object(qs.tg, "send"), \
             patch("requests.get") as mock_get:

            result = qs._download_ig_profile("testuser")

        mock_get.assert_not_called()
        assert len(result) == 1
        assert "ABC123.mp4" in result[0]

    def test_stops_downloading_at_size_limit(self, tmp_path):
        """累计大小超过 size_limit 后停止，不下载后续视频"""
        posts = [_make_post("V1"), _make_post("V2")]

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.iter_content.return_value = [b"x" * 200]  # 200 bytes per video
            return resp

        # 只让 SESSION_FILE 路径返回 True，其余走真实检查（tmp_path 里文件不存在 → 走下载路径）
        def exists_side_effect(path):
            return str(path) == str(qs.SESSION_FILE)

        with patch("os.path.exists", side_effect=exists_side_effect), \
             patch("instaloader.Instaloader"), \
             patch("instaloader.Profile.from_username") as mock_prof, \
             patch.object(qs, "DOWNLOAD_DIR", tmp_path), \
             patch.object(qs.tg, "send"), \
             patch("requests.get", side_effect=fake_get), \
             patch("time.sleep"):

            mock_prof.return_value.get_posts.return_value = iter(posts)
            result = qs._download_ig_profile("testuser", size_limit=150)

        assert len(result) == 1  # 第一个超限就停，不下第二个

    def test_raises_if_no_videos_found(self, tmp_path):
        """账号只有图片帖子，没有视频，应 raise RuntimeError"""
        mock_profile = MagicMock()
        mock_profile.get_posts.return_value = [_make_post("IMG1", is_video=False)]

        with patch("os.path.exists", return_value=True), \
             patch("instaloader.Instaloader"), \
             patch("instaloader.Profile.from_username", return_value=mock_profile), \
             patch.object(qs, "DOWNLOAD_DIR", tmp_path), \
             patch.object(qs.tg, "send"):

            with pytest.raises(RuntimeError, match="没有可下载的视频"):
                qs._download_ig_profile("testuser")

    def test_skips_failed_video_and_continues(self, tmp_path):
        """单个视频下载失败时跳过，继续处理后续视频"""
        posts = [_make_post("FAIL", video_url="http://example.com/fail.mp4"),
                 _make_post("OK01", video_url="http://example.com/ok.mp4")]

        def fake_get(url, **kwargs):
            if "fail" in url:
                raise ConnectionError("network error")
            resp = MagicMock()
            resp.iter_content.return_value = [b"x" * 100]
            return resp

        def exists_side_effect(path):
            return str(path) == str(qs.SESSION_FILE)

        with patch("os.path.exists", side_effect=exists_side_effect), \
             patch("instaloader.Instaloader"), \
             patch("instaloader.Profile.from_username") as mock_prof, \
             patch.object(qs, "DOWNLOAD_DIR", tmp_path), \
             patch.object(qs.tg, "send"), \
             patch("requests.get", side_effect=fake_get), \
             patch("time.sleep"):

            mock_prof.return_value.get_posts.return_value = iter(posts)
            result = qs._download_ig_profile("testuser")

        assert len(result) == 1
        assert "OK01" in result[0]


# ── _zip_videos ───────────────────────────────────────────────────────────────

class TestZipVideos:

    def test_zip_contains_all_videos(self, tmp_path):
        (tmp_path / "temp").mkdir()  # _zip_videos 写到 PROJECT_DIR/temp/
        videos = []
        for i in range(3):
            p = tmp_path / f"clip{i}.mp4"
            p.write_bytes(b"fake video")
            videos.append(str(p))

        with patch.object(qs, "PROJECT_DIR", tmp_path), \
             patch.object(qs.tg, "send"):
            zip_path = qs._zip_videos(videos, "testuser")

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        assert len(names) == 3
        assert all(n.endswith(".mp4") for n in names)

    def test_zip_filename_contains_username(self, tmp_path):
        (tmp_path / "temp").mkdir()
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x")

        with patch.object(qs, "PROJECT_DIR", tmp_path), \
             patch.object(qs.tg, "send"):
            zip_path = qs._zip_videos([str(p)], "myuser")

        assert "myuser" in os.path.basename(zip_path)


# ── _reply_bilibili ───────────────────────────────────────────────────────────

class TestReplyBilibili:

    def test_returns_false_when_no_cookie_file(self, tmp_path):
        with patch.object(qs, "COOKIE_FILE", tmp_path / "missing.json"):
            assert qs._reply_bilibili(1, 2, "msg") is False

    def test_returns_true_on_api_success(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps({"bili_jct": "csrf123", "SESSDATA": "abc"}))

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0}

        with patch.object(qs, "COOKIE_FILE", cookie_file), \
             patch("requests.Session") as mock_sess_cls:
            mock_sess = MagicMock()
            mock_sess.post.return_value = mock_resp
            mock_sess_cls.return_value = mock_sess

            result = qs._reply_bilibili(111, 222, "hello")

        assert result is True

    def test_returns_false_on_api_error_code(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps({"bili_jct": "csrf123"}))

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": -101}  # 未登录

        with patch.object(qs, "COOKIE_FILE", cookie_file), \
             patch("requests.Session") as mock_sess_cls:
            mock_sess = MagicMock()
            mock_sess.post.return_value = mock_resp
            mock_sess_cls.return_value = mock_sess

            result = qs._reply_bilibili(111, 222, "hello")

        assert result is False

    def test_returns_false_on_network_exception(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps({"bili_jct": "csrf123"}))

        with patch.object(qs, "COOKIE_FILE", cookie_file), \
             patch("requests.Session") as mock_sess_cls:
            mock_sess = MagicMock()
            mock_sess.post.side_effect = ConnectionError("timeout")
            mock_sess_cls.return_value = mock_sess

            result = qs._reply_bilibili(111, 222, "hello")

        assert result is False


# ── run() 主流程 ──────────────────────────────────────────────────────────────

class TestRun:

    def test_happy_path_without_rpid(self):
        mock_client = _make_quark_client()

        with patch.object(qs.tg, "send") as mock_tg, \
             patch.object(qs, "_download_ig_profile", return_value=["/tmp/v1.mp4"]), \
             patch.object(qs, "_zip_videos", return_value="/tmp/test.zip"), \
             patch.object(qs, "QuarkClient", return_value=mock_client), \
             patch("os.remove"):

            qs.run("testuser")

        messages = " ".join(str(c) for c in mock_tg.call_args_list)
        assert "分享完成" in messages
        assert "pan.quark.cn" in messages

    def test_download_failure_sends_error_and_stops(self):
        with patch.object(qs.tg, "send") as mock_tg, \
             patch.object(qs, "_download_ig_profile", side_effect=RuntimeError("没有视频")), \
             patch.object(qs, "_zip_videos") as mock_zip:

            qs.run("testuser")

        mock_zip.assert_not_called()
        messages = " ".join(str(c) for c in mock_tg.call_args_list)
        assert "下载失败" in messages

    def test_quark_cookie_expired_sends_specific_message(self):
        mock_client = MagicMock()
        mock_client.upload_folder = "粉丝定制"
        mock_client.get_or_create_folder.side_effect = PermissionError("expired")

        with patch.object(qs.tg, "send") as mock_tg, \
             patch.object(qs, "_download_ig_profile", return_value=["/tmp/v.mp4"]), \
             patch.object(qs, "_zip_videos", return_value="/tmp/test.zip"), \
             patch.object(qs, "QuarkClient", return_value=mock_client):

            qs.run("testuser")

        messages = " ".join(str(c) for c in mock_tg.call_args_list)
        assert "Cookie已过期" in messages

    def test_upload_failure_sends_error_and_stops(self):
        mock_client = MagicMock()
        mock_client.upload_folder = "粉丝定制"
        mock_client.get_or_create_folder.side_effect = Exception("upload error")

        with patch.object(qs.tg, "send") as mock_tg, \
             patch.object(qs, "_download_ig_profile", return_value=["/tmp/v.mp4"]), \
             patch.object(qs, "_zip_videos", return_value="/tmp/test.zip"), \
             patch.object(qs, "QuarkClient", return_value=mock_client):

            qs.run("testuser")

        messages = " ".join(str(c) for c in mock_tg.call_args_list)
        assert "上传夸克失败" in messages

    def test_zip_cleaned_up_after_success(self):
        mock_client = _make_quark_client()

        with patch.object(qs.tg, "send"), \
             patch.object(qs, "_download_ig_profile", return_value=["/tmp/v.mp4"]), \
             patch.object(qs, "_zip_videos", return_value="/tmp/test.zip"), \
             patch.object(qs, "QuarkClient", return_value=mock_client), \
             patch("os.remove") as mock_remove:

            qs.run("testuser")

        mock_remove.assert_called_once_with("/tmp/test.zip")

    def test_with_rpid_replies_to_bilibili(self, tmp_path):
        pending_file = tmp_path / "pending_comments.json"
        pending_file.write_text(json.dumps({
            "789": {"oid": 111, "rpid": 789, "uname": "粉丝甲", "bvid": "BV123"}
        }))
        mock_client = _make_quark_client()

        with patch.object(qs.tg, "send") as mock_tg, \
             patch.object(qs, "_download_ig_profile", return_value=["/tmp/v.mp4"]), \
             patch.object(qs, "_zip_videos", return_value="/tmp/test.zip"), \
             patch.object(qs, "QuarkClient", return_value=mock_client), \
             patch.object(qs, "PENDING_FILE", pending_file), \
             patch.object(qs, "_reply_bilibili", return_value=True) as mock_reply, \
             patch("os.remove"):

            qs.run("testuser", rpid="789")

        mock_reply.assert_called_once()
        messages = " ".join(str(c) for c in mock_tg.call_args_list)
        assert "已在 B站回复" in messages

    def test_with_rpid_but_no_pending_context_skips_reply(self, tmp_path):
        pending_file = tmp_path / "pending_comments.json"
        pending_file.write_text(json.dumps({}))
        mock_client = _make_quark_client()

        with patch.object(qs.tg, "send") as mock_tg, \
             patch.object(qs, "_download_ig_profile", return_value=["/tmp/v.mp4"]), \
             patch.object(qs, "_zip_videos", return_value="/tmp/test.zip"), \
             patch.object(qs, "QuarkClient", return_value=mock_client), \
             patch.object(qs, "PENDING_FILE", pending_file), \
             patch.object(qs, "_reply_bilibili") as mock_reply, \
             patch("os.remove"):

            qs.run("testuser", rpid="999")

        mock_reply.assert_not_called()
        messages = " ".join(str(c) for c in mock_tg.call_args_list)
        assert "未找到" in messages
