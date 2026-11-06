"""Source-style prompt record selection and stable user/experiment cohorts."""
import hashlib
def get_prompt_record(templates,name,version):
    """Return the selected PromptTemplate record within its named version map.

    This local service uses explicit deployed versions; missing names/versions
    raise KeyError rather than silently borrowing another family or v1.
    """
    return templates[name][version]
def stable_bucket(user,experiment_id):
    """Return source MD5(user:experiment-id) mod100, independent of process hash seed."""
    return int(hashlib.md5((user+":"+experiment_id).encode("utf-8")).hexdigest(),16)%100
