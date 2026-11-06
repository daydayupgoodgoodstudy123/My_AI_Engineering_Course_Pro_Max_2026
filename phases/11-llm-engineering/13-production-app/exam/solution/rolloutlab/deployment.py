"""Static configuration evidence over the actual template-name/version registry."""
from .contracts import validate_deployment,registered_model
def deployment_report(templates,experiments,models,primary_model):
    """Report every deployed record identity/model and scoped experiment reference.

    Primary_model is context, not a substitute for a record's actual model.
    Check outer name/version against each record; retain every issue's full source
    configuration path in traversal order. Resolve control/variant only inside
    the experiment's declared template, without runtime v1 fallback. Every
    sibling is visited. Experiment valid means its references exist; each version
    separately reports its record validity. Unknown template experiments go under
    unresolved_experiments. configuration_ready means static consistency only,
    not provider availability/health or a dependency DAG. Primitive shape/model
    recognizer is correct and supplied. Inputs remain unchanged.
    """
    validate_deployment(templates,experiments)
    result={"configuration_ready":True,"templates":{},"unresolved_experiments":{},"issues":[]}
    def issue(path,code):
        value={"path":path,"code":code};result["issues"].append(value);return value
    for name,versions in templates.items():
        reports={}
        for version,record in versions.items():
            problems=[]
            if record.name!=name:problems.append(issue(("templates",name,version,"name"),"record_name"))
            if record.version!=version:problems.append(issue(("templates",name,version,"version"),"record_version"))
            if not registered_model(record.model,models):problems.append(issue(("templates",name,version,"model"),"unknown_model"))
            reports[version]={"valid":not problems,"record":record,"issues":problems}
        result["templates"][name]={"versions":reports,"experiments":{}}
    for experiment_id,experiment in experiments.items():
        problems=[];paths={}
        if experiment.template not in templates:
            problems.append(issue(("experiments",experiment_id,"template"),"missing_template"))
        else:
            for label,version in (("control",experiment.control),("variant",experiment.variant)):
                if version not in templates[experiment.template]:problems.append(issue(("experiments",experiment_id,label),"missing_"+label))
                else:paths[label]=( "templates",experiment.template,version)
        entry={"valid":not problems,"control_path":paths.get("control"),"variant_path":paths.get("variant"),"issues":problems}
        if experiment.template in result["templates"]:result["templates"][experiment.template]["experiments"][experiment_id]=entry
        else:result["unresolved_experiments"][experiment_id]=entry
    result["configuration_ready"]=not result["issues"]
    return result
