"""
CAM — AI 驱动的复利记忆系统

让知识越积累越值钱。

安装:
    pip install cam

快速开始:
    cam init my-wiki
    cd my-wiki
    # 把资料扔进 raw/
    cam ingest
    cam stats

作为 Python 库使用:
    from cam_core import MemoryCore
    
    mc = MemoryCore(wiki_path="./wiki")
    await mc.initialize()
    result = await mc.remember(user_message, ai_response)
"""

__version__ = "2.0.0"
