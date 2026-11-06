"""Local tool registration and result dispatch with caller-owned fixture data."""
from .tool_contracts import valid_tool_args
def install_handlers(handlers):
    """Register every name against its own supplied callable."""
    registry={}
    for name,handler in handlers.items():registry[name]=lambda args:handler(args)
    return registry
def format_weather(row,args):
    """Given consumer of the declared weather-tool result contract."""
    field="temp_f" if args.get("units","celsius")=="fahrenheit" else "temp_c"
    return {"city":row["city"],field:row[field],"condition":row["condition"]}
class ToolService:
    def __init__(self):
        self.weather_rows={"tokyo":{"temp_c":18,"condition":"cloudy"},"london":{"temp_c":12,"condition":"rainy"}}
        self.files={"README.md":"local tools","资料.md":"温度\r\n例"}
        self.registry=install_handlers({"weather":self.weather,"read_file":self.read_file,"search":self.search})
    def weather(self,args):
        """Return one converted weather result without changing the fixture row."""
        key=args["city"].strip().lower()
        if key not in self.weather_rows:return {"error":True,"code":"CITY_NOT_FOUND"}
        data=self.weather_rows[key]
        if args.get("units","celsius")=="fahrenheit":data["temp_f"]=round(data.pop("temp_c")*9/5+32,1)
        data["city"]=args["city"];return data
    def search(self,args):
        """Given offline local search fixture, with no network access."""
        query=args.get("query","")
        return {"query":query,"results":["Function calling guide"] if "tool" in query.lower() else []}
    def read_file(self,args):
        """Given exact allowlisted in-memory file response and UTF8 size."""
        path=args["path"]
        if path not in self.files:return {"error":True,"code":"NOT_FOUND"}
        text=self.files[path];return {"path":path,"content":text,"size_bytes":len(text.encode("utf-8"))}
    def execute(self,name,args):
        """Given indexed dispatch and weather result rendering."""
        if name not in self.registry:return {"error":True,"code":"UNKNOWN_TOOL"}
        result=self.registry[name](args)
        if name=="weather" and not result.get("error",False):return format_weather(result,args)
        return result
    def call(self,name,args):
        if not valid_tool_args(name,args):return {"error":True,"code":"INVALID_ARGS"}
        return self.execute(name,args)
