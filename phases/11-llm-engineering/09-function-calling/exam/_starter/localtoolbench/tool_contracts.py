"""Given known local-tool argument boundary, not a general schema compiler."""
def valid_tool_args(name,args):
    if type(args) is not dict:return False
    required={"weather":{"city"},"search":{"query"},"read_file":{"path"}}
    if name not in required:return True
    fields=required[name];allowed=fields|({"units"} if name=="weather" else set())
    if not fields<=set(args)<=allowed or any(type(value) is not str for value in args.values()):return False
    return name!="weather" or args.get("units","celsius") in {"celsius","fahrenheit"}
