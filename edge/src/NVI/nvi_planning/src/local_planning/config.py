import json


class SemanticConfig:
    '''
    key: color in tuple type
    value: label in dict type
    '''
    def __init__(self):
        self.config_color = {}
        pass

    def parse_json(self,filepath):
        with open(filepath, encoding='utf-8') as file:
            json_file = json.load(file)
            labels = json_file.get('labels')
            for label in labels:
                color = tuple(label['color'])
                self.config_color[color] = {}
                self.config_color[color]['name'] = label['name']
                self.config_color[color]['readable'] = label['readable']
                self.config_color[color]['degree'] = label['degree']
                self.config_color[color]['height_independent'] = label['height_independent']
                self.config_color[color]['macro'] = label['name'].split('--')[-2]


    def get_degree(self,color):
        label  = self.config_color.get(color)
        if label is None:
            print('warning: not found color', color)
            return
        return label.get('degree')

    def get_name(self,color):
        label = self.config_color.get(color)
        if label is None:
            print('warning: not found color', color)
            return
        return label.get('readable')

    def get_macro(self,color):
        label = self.config_color.get(color)
        if label is None:
            print('warning: not found color', color)
            return
        return label.get('macro')

    def get_super_name(self, color):
        label = self.config_color.get(color)
        if label is None:
            print('warning: not found color', color)
            return
        return label.get('name')
    
    def get_height_independent(self, color):
        label = self.config_color.get(color)
        if label is None:
            print('warning: not found color', color)
            return
        return label.get('height_independent')
    
    def get_semantic(self, color):
        label = self.config_color.get(color, None)
        return label

class MetricConfig:
    def __init__(self, method=0):
        self.set_method(method)

    def set_method(self,method):
        self.method = method
        if method == 0:
            self.curve = self.curve0
        elif method == 1:
            self.curve = self.curve1
        else:
            self.curve = self.curve0
            self.method = 0
            print('invalid method', method,
                  ', already set method to default method 0.')

    @staticmethod
    def curve0(m):
        if m < -0.2 and m > -2.5:
            return 1
        return 0

    @staticmethod
    def curve1(m):
        if m <= -0.4 and m > -2.5:
            return 1
        elif m<= -0.2 and m > -0.4:
            return 1-((m+0.4)/0.2)**2
        return 0
        
    def get_degree(self, m):
        return self.curve(m)

if __name__ == '__main__':
    sc = SemanticConfig()
    sc.parse_json(
        "./nvi_planning/src/local_planning/config/dataconfig_mapillary_extend.json")
    print(sc.get_name((230,150,140)))
    print(sc.get_macro((230, 150, 140)))
    macro = []
    for key, value in sc.config_color.items():
        if value.get('macro') not  in macro:
            macro.append(value.get('macro'))
    for e in macro:
        print('("%s",0),'%e,end="")
    print("")
    # print(macro)
