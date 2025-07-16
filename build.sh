#!/bin/bash
# 用python -m venv venv 创建虚拟环境
# source venv/bin/activate
# 然后pip install -r requirements.txt
# bash build.sh 打包
# 不用 uv 弄的环境，会报错
find . -name "._.DS_Store" -type f -delete
find . -name ".DS_Store" -type f -delete
git rm --cached $(git ls-files --deleted) # git 删除（下一步commit）
rm -rf build/ dist/
#python setup.py py2app -A
python setup.py py2app -p pygments
