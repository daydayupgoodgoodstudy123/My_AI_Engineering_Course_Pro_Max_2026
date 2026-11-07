"""Three independent candidate algorithms: action interpretation, subject prediction and own actual-view choice."""
from .models import SubjectModel
from .codec import prediction
from .reasoning_support import subject_actions,validate_prior
def build_other_models(snapshot,observer,now,completed):
    """Interpret each subject's real visible approach actions against that subject's own prior, preserving perceived alternatives."""
    models=[]
    for prior in snapshot.priors:
        validate_prior(prior);believed=list(prior.believed_available);preference=list(prior.preference);sources=[];last=None
        for action in subject_actions(snapshot,observer,prior.subject,now):
            target=action.value
            if target not in believed:believed.append(target)
            preference=[target]+[box for box in preference if box!=target];sources.append(action.uid);last=action.turn
        models.append(SubjectModel(prior.subject,tuple(believed),tuple(preference),prior.subject not in completed,last,tuple(sources)))
    return tuple(models)
def predict_subject_target(model):
    """Predict from the subject's perceived candidates and own preference, including an internally consistent false belief."""
    if not model.active or not model.believed_available:return prediction(model,None)
    target=next((box for box in model.preference if box in model.believed_available),model.believed_available[0])
    return prediction(model,target)
def choose_own_target(actual_view,predictions,rng):
    """Exclude predicted other targets from the real current inventory, with a same-inventory fallback and exact RNG usage."""
    if not actual_view.boxes:return None
    excluded={p.target for p in predictions if p.target is not None};options=tuple(box for box in actual_view.boxes if box not in excluded)
    return rng.choice(options or actual_view.boxes)
