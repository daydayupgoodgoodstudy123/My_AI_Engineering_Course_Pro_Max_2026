"""GIVEN dbm UTF8/JSON storage and stable record-key framing."""
import dbm,json

class ConfigDatabase:
    def __init__(self,path):self.db=dbm.open(str(path),'c')
    def close(self):self.db.close()

    def put(self,kind,name,value):
        key=json.dumps([kind,name],ensure_ascii=False,separators=(',',':')).encode('utf-8')
        self.db[key]=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')

    def get(self,kind,name):
        key=json.dumps([kind,name],ensure_ascii=False,separators=(',',':')).encode('utf-8')
        return json.loads(self.db[key].decode('utf-8'))
