# 安装

## PaddleOCR
需要安装[PaddlePaddle](https://www.paddlepaddle.org.cn/install/quick?docurl=/documentation/docs/zh/install/pip/linux-pip.html)和[PaddleOCR2.6](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.6/doc/doc_en/quickstart_en.md)
需要额外安装cuDNN，可以参考网上安装方法。

## PyKDL

1. 可能会出现安装tf2_ros时没有安装PyKDL的情况，请使用conda安装:
```
conda install python-orocos-kdl -c conda-forge
```

# 配置文件
1. 相机内参fx, fy, cx, cy, height, width
2. 控制该模块运行的topic，以及开始运行的期望消息，类型为string。
3. 具体设置：语言、是否使用gpu、发布topic等

如果开启可视化检测结果，需要下载字体文件[simfang.ttf](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.6/doc/fonts/simfang.ttf)到scripts文件夹下。

# 具体细节

## 控制方式
在控制topic中发布期望字符串就可以开启ocr模块，当在该topic中接收到非期望字符串时，ocr模块会关闭，等待下次开启。

## 输出格式
使用HeaderString，Header中的stamp与rbg图像相同，frame_id为vio的全局坐标系（world）。
String部分为可解码json字符串，解码后为一个list，list中每个元素都是一个五元组，前三个分别是xyz坐标，第四个是检测到的文本，第五个是0～1的置信度。