"""
单独执行：等审核通过 → 发章节评论 → 置顶
用于视频已上传但评论还没发的情况
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ACCOUNT_NAME = "ai_vanvan"
VIDEO_TITLE   = "ins海外离大谱#237"
CHAPTER_LIST  = """00:00  bby.bri.xox
00:11  brittneykakalia
00:25  lanetkelveiffetsiz
00:34  hadleyreacts
00:45  catsara.love
00:55  kailynklein103
01:01  ariazeiiin
01:11  segredoflix.br
01:18  elmello_billar_tv
01:29  anything_explainology
01:38  __behruz__30__
01:45  beachbeauty.magazine"""

from src.platforms.bilibili.uploader import BilibiliUploader

uploader = BilibiliUploader(ACCOUNT_NAME)
if not uploader.setup_driver():
    print("❌ 浏览器启动失败")
    sys.exit(1)

# 注入标题和章节，直接跑等审核+发评论流程
uploader._upload_title = VIDEO_TITLE
uploader._wait_review_then_comment(CHAPTER_LIST)
