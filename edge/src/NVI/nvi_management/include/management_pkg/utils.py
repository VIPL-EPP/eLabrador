import string, zhon, re, dimsim
import roslib.packages
import os

MANAGEMENT_DIR = roslib.packages.get_pkg_dir("nvi_management")
CONFIG_DIR = os.path.join(MANAGEMENT_DIR, "config")

def remove_punctuation(text):
    punctuation = string.punctuation + zhon.hanzi.punctuation
    return re.sub('[{}]'.format(punctuation), "", text)
    
def calculate_text_distance(textA: str, textB: str):
    if len(textA)!=len(textB):
        return 100
    dis=0.0
    try:
        for a, b in zip(textA, textB):
            if '\u4e00' <= a <= '\u9fff' and '\u4e00' <= b <= '\u9fff':
                dis += dimsim.get_distance(a, b)
            else:
                dis += (a!=b)
    except Exception as e:
        return 100
    return dis