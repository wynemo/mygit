
pyqt6-dev-tools  ubuntu 安装 pylupdate6
qt6-l10n-tools ubuntu 安装 lrelease

```bash
root@c436c3c73206:/app# pylupdate6 git_manager_window.py -ts translations/app_zh_CN.ts
Summary of changes to translations/app_zh_CN.ts:
    1 new messages were added
    1 existing messages were found
root@c436c3c73206:/app# /usr/lib/qt6/bin/lrelease translations/app_zh_CN.ts
Updating 'translations/app_zh_CN.qm'...
    Generated 2 translation(s) (2 finished and 0 unfinished)
```