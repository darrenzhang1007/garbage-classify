'''
@Author: DarrenZhang
@Date: 2020-05-25 18:52:01
@LastEditTime: 2020-05-31 10:09:21
@Description: flask server garbage
@FilePath: /garbage-classify/app_garbage.py
'''
import torch
import cv2 
from flask import Flask, request
from flask import render_template
import os
from utils.json_utils import jsonify
from utils.train_eval import initital_model, class_id2name
from utils.transform import transform_image, preprocess

import time
import json
from collections import OrderedDict
import codecs
from args import args
from PIL import Image


# 获取所有配置参数
state = {k: v for k, v in args._get_kwargs()}
print("state = ", state)

app = Flask(__name__)
# 设置编码-否则返回数据中文时候-乱码
app.config['JSON_AS_ASCII'] = False
# 加载Label2Name Mapping
class_id2name = {}
for line in codecs.open('data/garbage_label.txt', 'r', encoding='utf-8'):
    line = line.strip()
    _id = line.split(":")[0]
    _name = line.split(":")[1]
    class_id2name[int(_id)] = _name

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')  # 设备
print('Pytorch garbage-classification Serving on {} ...'.format(device))
num_classes = len(class_id2name)
model_name = args.model_name
model_path = args.resume # --resume checkpoint/garbage_resnext101_model_2_1111_4211.pth
print("model_name = ", model_name)
print("model_path = ", model_path)

model_ft = initital_model(model_name, num_classes, feature_extract=True)
model_ft.to(device)  # 设置模型运行环境
# 指定map_location='cpu' ，GPU 环境下训练的模型可以在CPU环境加载并使用[本地测试CPU可以测试，线上环境GPU模型]
model_ft.load_state_dict(torch.load(model_path, map_location='cuda'))
model_ft.eval()

system_path = "./"
@app.route('/')
def hello(imgPath=None):
    return render_template('index.html', imgPath="./static/image/logo.jpg")

@app.route('/img_show')
def img_show(imgPath=None):
    imgPath = os.path.join("./static/image", imgPath)
    print(imgPath)
    return  imgPath 

@app.route('/predict', methods=['POST'])
def predict(imgPath=None, result="None"):
    # 获取输入数据
    file = request.files['content']
    fileName = file.filename
    filePath = "static/image/" + fileName  
    print(filePath)
    if file:
        file.save(filePath)

    # img_bytes = file.read()
    img_bytes = cv2.imread(filePath)
    img_bytes = Image.fromarray(img_bytes)

    # 特征提取
    feature = preprocess(img_bytes).unsqueeze(0)
    feature = feature.to(device)  # 在device 上进行预测

    # 模型预测
    with torch.no_grad():
        t1 = time.time()
        outputs = model_ft.forward(feature)
        consume = (time.time() - t1) * 1000
        consume = int(consume)

    # API 结果封装
    label_c_mapping = {}
    ## The output has unnormalized scores. To get probabilities, you can run a softmax on it.
    ## 通过softmax 获取每个label的概率
    outputs = torch.nn.functional.softmax(outputs[0], dim=0)
    pred_list = outputs.cpu().numpy().tolist()

    for i, prob in enumerate(pred_list):
        label_c_mapping[int(i)] = prob
        
    ## 按照prob 降序，获取topK = 5
    dict_list = []
    for label_prob in sorted(label_c_mapping.items(), key=lambda x: x[1], reverse=True)[:5]:
        label = int(label_prob[0])
        result = {'label': label, 'c': label_prob[1], 'name': class_id2name[label]}
        dict_list.append(result)

    ## dict 中的数值按照顺序返回结果
    result = OrderedDict(error=0, errmsg='success', consume=consume, data=dict_list)
    result_dict = {}
    result_dict["consume"] = consume
    result_dict["label"] = dict_list[0]['name']
    return json.dumps(result_dict, ensure_ascii=False)
 
    # return jsonify(result)
    # result = dict_list[0]['name']
    # print(result)
    # if result is None:
    #     result = "could not found your pic"
    # # return result, consume
    # return render_template('index.html', imgPath="./static/image/" + fileName,
    #                         result=result, time=consume)
    
    # return jsonify(result)


if __name__ == '__main__':
    # curl -X POST -F file=@cat_pic.jpeg http://localhost:5000/predict
    app.run(host="172.17.56.5", port=90, debug=True)


# nohup python app_garbage_server1.py --model_name resnext101_32x16d --resume checkpoint/garbage_resnext101_model_7_9591_9574.pth -log=stdout &
