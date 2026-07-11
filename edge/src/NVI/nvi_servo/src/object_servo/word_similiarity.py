import gensim
import pkuseg
import numpy as np
from numpy.linalg import norm
import distance
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


class SentenceSim:
    def __init__(self,vector_sim=False, jaccard_sim = False, tf_sim=False, tfidf_sim=False) -> None:
        self.vector_sim = vector_sim
        self.jaccard_sim = jaccard_sim
        self.tf_sim = tf_sim
        self.tfidf_sim = tfidf_sim
        if self.vector_sim:
            self.model_file_name = CURRENT_DIR+'/word2vec/news_12g_baidubaike_20g_novel_90g_embedding_64.bin'
            self.vector_model = gensim.models.KeyedVectors.load_word2vec_format(self.model_file_name, binary=True)
        if self.tf_sim or self.jaccard_sim:
            self.tf_model = CountVectorizer(tokenizer=lambda s: ' '.join(list(s)).split())
        if self.tfidf_sim:
            self.tfidf_model = TfidfVectorizer(tokenizer=lambda s: ' '.join(list(s)).split())
        self.sentence_seg = pkuseg.pkuseg()
        self.sentence2vector_buffer = {}

    def vector_similarity(self, s1, s2):
        if not self.vector_sim:
            raise ValueError('Vector similarity is not enabled.')
        if s1 not in self.sentence2vector_buffer:
            self.sentence2vector_buffer[s1] = self.sentence2vector(s1)
        if s2 not in self.sentence2vector_buffer:
            self.sentence2vector_buffer[s2] = self.sentence2vector(s2)
        v1, v2 = self.sentence2vector_buffer[s1], self.sentence2vector_buffer[s2]
        return np.dot(v1, v2) / (norm(v1) * norm(v2))

    def sentence2vector(self, s):
        words = self.sentence_seg.cut(s)
        v = np.zeros(64)
        for word in words:
            v += self.vector_model[word]
        v /= len(words)
        return v
    
    def edit_similarity(self, s1, s2):
        return distance.levenshtein(s1, s2)
    
    def jaccard_similarity(self, s1, s2):
        if not self.jaccard_sim:
            raise ValueError('Jaccard similarity is not enabled.')
        corpus = [s1, s2]
        vectors = self.tf_model.fit_transform(corpus).toarray()
        numerator = np.sum(np.min(vectors, axis=0))
        denominator = np.sum(np.max(vectors, axis=0))
        return 1.0 * numerator / denominator
    
    def tf_similarity(self, s1, s2):
        if not self.tf_sim:
            raise ValueError('TF similarity is not enabled.')
        corpus = [s1, s2]
        vectors = self.tf_model.fit_transform(corpus).toarray()
        return np.dot(vectors[0], vectors[1]) / (norm(vectors[0]) * norm(vectors[1]))

    def tfidf_similarity(self, s1, s2):
        if not self.tfidf_sim:
            raise ValueError('TFIDF similarity is not enabled.')
        corpus = [s1, s2]
        vectors = self.tfidf_model.fit_transform(corpus).toarray()
        return np.dot(vectors[0], vectors[1]) / (norm(vectors[0]) * norm(vectors[1]))

if __name__ == '__main__':
    import time
    t0 = time.perf_counter()
    sentence_sim = SentenceSim(vector_sim=True,jaccard_sim=True,tf_sim=True,tfidf_sim=True)
    print('load cost',time.perf_counter()-t0)
    s1 = '视觉伺服节点'
    s2 = '对象伺服节点'
    t0 = time.perf_counter()
    sim = sentence_sim.vector_similarity(s1,s2)
    print('vector sim cost',time.perf_counter()-t0)
    print(sim)
    t0 = time.perf_counter()
    sim = sentence_sim.jaccard_similarity(s1,s2)
    print('jaccard sim cost',time.perf_counter()-t0)
    print(sim)
    t0 = time.perf_counter()
    sim = sentence_sim.tf_similarity(s1,s2)
    print('tf sim cost',time.perf_counter()-t0)
    print(sim)
    t0 = time.perf_counter()
    sim = sentence_sim.tfidf_similarity(s1,s2)
    print('tfidf sim cost',time.perf_counter()-t0)
    print(sim)
    t0 = time.perf_counter()
    sim = sentence_sim.edit_similarity(s1,s2)
    print('edit sim cost',time.perf_counter()-t0)
    print(sim)


    



 

    