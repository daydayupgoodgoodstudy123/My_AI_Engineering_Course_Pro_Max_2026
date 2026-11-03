SPEC = dict(
 title="Persist a task state machine", zh_title="持久化任务状态机", level="中等",
 brief="在提供好的 JSON 存储基础上补全任务创建和状态转换。测试会重新打开存储，确认结果没有只停留在内存。",
 scenario="A worker restarts between requests. Complete durable task creation and legal transitions using the provided persistence helper.",
 contract="""TaskStore(path) loads a JSON dict or starts empty. create(task_id,owner) creates {'id':task_id,'owner':owner,'status':'queued'}, persists it, and returns a copy. Duplicate task id raises ValueError without changing existing state. transition(task_id,owner,status) returns a copied updated record after persisting. Unknown task OR mismatched owner raises KeyError. Allowed transitions: queued -> working or canceled; working -> completed, failed, or canceled. All other transitions, including terminal repeats, raise ValueError with no state change. get(task_id) is provided for inspection. ids and owners are nonempty strings; persistence errors are outside this exercise's fault model. _persist is already supplied.""",
 bonus="purge_terminal() deletes all completed/failed/canceled records, persists once, returns sorted removed ids, and preserves queued/working tasks.",
 stubs=["TaskStore.create", "TaskStore.transition", "TaskStore.purge_terminal"],
 code=r'''import json
from pathlib import Path
class TaskStore:
    def __init__(self,path):
        self.path=Path(path);self.tasks=json.loads(self.path.read_text()) if self.path.exists() else {}
    def _persist(self):
        temporary=self.path.with_suffix(".tmp");temporary.write_text(json.dumps(self.tasks,sort_keys=True));temporary.replace(self.path)
    def get(self,task_id):return self.tasks[task_id].copy()
    def create(self,task_id,owner):
        if task_id in self.tasks:raise ValueError("duplicate")
        self.tasks[task_id]={"id":task_id,"owner":owner,"status":"queued"};self._persist();return self.get(task_id)
    def transition(self,task_id,owner,status):
        if task_id not in self.tasks or self.tasks[task_id]["owner"]!=owner:raise KeyError(task_id)
        allowed={"queued":{"working","canceled"},"working":{"completed","failed","canceled"}}
        if status not in allowed.get(self.tasks[task_id]["status"],set()):raise ValueError("transition")
        self.tasks[task_id]["status"]=status;self._persist();return self.get(task_id)
    def purge_terminal(self):
        ids=sorted(k for k,v in self.tasks.items() if v["status"] in ("completed","failed","canceled"))
        for k in ids:del self.tasks[k]
        self._persist();return ids
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/"tasks.json";self.s=m.TaskStore(self.path)
    def test_create_restart(self):
        self.assertEqual(self.s.create("t","a"),{"id":"t","owner":"a","status":"queued"})
        self.assertEqual(m.TaskStore(self.path).get("t")["status"],"queued")
    def test_duplicate(self):
        self.s.create("t","a")
        with self.assertRaises(ValueError):self.s.create("t","b")
        self.assertEqual(m.TaskStore(self.path).get("t")["owner"],"a")
    def test_complete_restart(self):
        self.s.create("t","a");self.s.transition("t","a","working");self.s.transition("t","a","completed")
        self.assertEqual(m.TaskStore(self.path).get("t")["status"],"completed")
    def test_invalid_no_change(self):
        self.s.create("t","a")
        with self.assertRaises(ValueError):self.s.transition("t","a","completed")
        self.assertEqual(m.TaskStore(self.path).get("t")["status"],"queued")
    def test_ownership_and_unknown(self):
        self.s.create("t","a")
        for task,owner in (("t","b"),("missing","a")):
            with self.subTest(task=task),self.assertRaises(KeyError):self.s.transition(task,owner,"working")
    def test_terminal_and_copy(self):
        self.s.create("t","a")["status"]="bad";self.s.transition("t","a","canceled")
        with self.assertRaises(ValueError):self.s.transition("t","a","working")
class BonusTests(unittest.TestCase):
    setUp=CoreTests.setUp
    def test_purge(self):
        self.s.create("z","a");self.s.create("a","a");self.s.transition("z","a","canceled")
        self.assertEqual(self.s.purge_terminal(),["z"]);self.assertEqual(m.TaskStore(self.path).get("a")["status"],"queued")
''',
 followups=["真实多进程 worker 为什么不能直接共用这个 JSON 文件？", "取消请求和任务已经停止执行之间有什么区别？"],
 explanation="终态不可逆；所有成功写操作都持久化后再返回。临时文件替换只解决本题单进程写入，不声称提供多进程事务。"
)
