"""Three independent candidate algorithms: action interpretation, subject prediction and own actual-view choice."""
from .models import SubjectModel
from .codec import prediction
from .reasoning_support import subject_actions,validate_prior
def build_other_models(snapshot,observer,now,completed):
    """Interpret each subject's real visible approach actions against that subject's own prior, preserving perceived alternatives."""
    raise NotImplementedError
def predict_subject_target(model):
    """Predict from the subject's perceived candidates and own preference, including an internally consistent false belief."""
    raise NotImplementedError
def choose_own_target(actual_view,predictions,rng):
    """Exclude predicted other targets from the real current inventory, with a same-inventory fallback and exact RNG usage."""
    raise NotImplementedError
