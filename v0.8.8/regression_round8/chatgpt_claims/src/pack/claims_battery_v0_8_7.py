#!/usr/bin/env python3
"""Claims battery for Humble Seed v0.8.7: a scaffold for checking whether each documented claim
in the candidate's docstring is accurate as stated.

The claims are in CLAIMS.json, quoted verbatim from the docstring. For each claim there is one
check_<ID>(d) function below. Fill it in, so that it returns:
    {"verdict": "HOLDS" | "HOLDS WITH CAVEATS" | "WRONG" | "NOT TESTED",
     "evidence": <anything JSON-serializable: what you ran and what it returned>}
Open questions QA, QB and QC have check_QA, check_QB and check_QC; a "verdict" there is "FOUND" or "NOT FOUND".
Anything else you find goes in a function named extra_<name>(d); it is run and reported too.

Each function gets a fresh, empty temporary directory d (a pathlib.Path).
Run:  python3 -I claims_battery_v0_8_7.py
Output: a table on stdout, and CLAIMS_RESULTS_v0_8_7.json next to this file.
"""
import importlib.util, json, os, stat, subprocess, sys, tempfile, threading, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAND = HERE / "humble_seed_v0_8_7_candidate.py"
CLAIMS = json.loads((HERE / "CLAIMS.json").read_text())


def _load(path, alias):
    spec = importlib.util.spec_from_file_location(alias, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m          # needed: the candidate defines dataclasses
    spec.loader.exec_module(m)
    return m


K = _load(CAND, "hs087")

# ---------------------------------------------------------------------------
# Helpers (use, change or ignore them; nothing below is part of the candidate)
# ---------------------------------------------------------------------------
PREF = "I always prefer shorter answers"   # the stub interpreter reads this as a preference -> a proposal
PLAIN = "hmm ok"                           # read as unclear -> the organism dwells (a non-authorizing event)


def born(d):
    """A hatched organism whose genesis the owner has attested. Returns (seed, owner)."""
    seed = K.HumbleSeed(d / "org")
    _, pem, _ = seed.hatch()
    owner = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    assert owner.attest(seed) is True
    return seed, owner


def reading(seed, category="verbosity"):
    r = seed.dwell_or_propose(category, "evt", PREF)
    assert r["status"] == "proposal", r["status"]
    return r


def apply(seed, owner, r, attest=True):
    """Owner signs the reading; organism applies it; optionally the owner attests the result."""
    res = seed.authorize_and_apply(r["proposal_id"], owner.sign_proposal(r["payload_to_sign"]))
    assert res is not None, seed.trace[-1]
    if attest:
        assert owner.attest(seed) is True
    return res


def dwell(seed, category="formality"):
    r = seed.dwell_or_propose(category, "evt", PLAIN)
    assert r["status"] == "dwelling", r["status"]
    return r


def reload(seed_or_dir):
    """A new organism object loaded from the saved file (raises if the file does not load)."""
    data_dir = seed_or_dir.data_dir if hasattr(seed_or_dir, "data_dir") else Path(seed_or_dir)
    f = K.HumbleSeed(data_dir)
    f.load()
    return f


def saved(seed):
    """The organism's saved file, parsed."""
    return json.loads(seed._state_path().read_text())


def reopen_owner(owner):
    """A new owner session over the same witness file and key."""
    return K.OwnerTool(owner._pem, K.OwnerWitness(owner.witness.path))


def witness_seq(owner, seed):
    return K.OwnerWitness(owner.witness.path).ledger[seed.organism_id]["sequence"]


def intent_pending(owner, seed):
    return K.OwnerWitness(owner.witness.path).pending_for(seed.organism_id) is not None


def outcome(fn):
    """Run fn(); return what it returned or what it raised, as data."""
    try:
        return {"returned": fn()}
    except Exception as e:
        return {"exception": type(e).__name__, "message": str(e)}


LOADER = ("import importlib.util, sys\n"
          "spec = importlib.util.spec_from_file_location('hs087', sys.argv[1])\n"
          "K = importlib.util.module_from_spec(spec); sys.modules['hs087'] = K; spec.loader.exec_module(K)\n")


def python_subprocess(code, *args, timeout=300, wait=True):
    """Run `LOADER + code` in a separate Python process. Inside it, K is the candidate and
    sys.argv[2:] are *args (as strings). With wait=False, returns the Popen object."""
    cmd = [sys.executable, "-I", "-c", LOADER + code, str(CAND), *map(str, args)]
    if not wait:
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {"rc": p.returncode, "stdout": p.stdout[-4000:], "stderr": p.stderr[-4000:]}


NOT_TESTED = {"verdict": "NOT TESTED", "evidence": None}


# Independent executable checks. The candidate is never edited.
import copy, signal, hashlib, contextlib


def answer(verdict, **evidence):
    return {"verdict": verdict, "evidence": evidence}


def capture(fn):
    """Also capture the deliberately injected KeyboardInterrupt in U2."""
    try:
        return {"returned": fn()}
    except BaseException as e:
        return {"exception": type(e).__name__, "message": str(e)}


def memory(s):
    return copy.deepcopy({
        "organism_id": s.organism_id, "generation": s._generation,
        "character": s.character, "trace": s.trace, "head": s._trace_head,
        "basin": [K.asdict(x) for x in s.basin],
        "pending": {k: K.asdict(v) for k, v in s.pending.items()},
        "consumed": sorted(s.consumed), "category_sequence": s.category_sequence,
        "mutation_sequence": s.mutation_sequence,
        "checkpoint": K.asdict(s.checkpoint) if s.checkpoint else None,
        "checkpoint_sig": s.checkpoint_sig})


def lock_owned(s):
    entry = K._OwnerLock._registry.get(os.path.abspath(str(s.data_dir / 'organism.lock')))
    return bool(entry and entry['depth'] > 0 and entry['rlock']._is_owned())


def require_exception(r, kind):
    assert r.get('exception') == kind, r


def _callback_write(d):
    s, o = born(d)
    r = reading(s)
    sig = o.sign_proposal(r['payload_to_sign'])
    other = reload(s)
    before = memory(s)
    seen = {}
    def reader(*args):
        seen['lock_owned'] = lock_owned(s)
        dwell(other, 'curiosity')
        seen['saved_after_callback'] = saved(s)
        return None
    s.reader = reader
    result = outcome(lambda: s.authorize_and_apply(r['proposal_id'], sig))
    after = memory(s)
    disk = saved(s)
    require_exception(result, 'StaleOrganism')
    assert seen['lock_owned'] and disk == seen['saved_after_callback']
    assert before['character'] != after['character']
    assert disk['character'] == before['character']
    return {'run': 'reader calls dwell(other object), then outer authorize_and_apply resumes',
            'outer_result': result, 'callback_lock_owned': seen['lock_owned'],
            'memory_character_before': before['character'],
            'memory_character_after_refusal': after['character'],
            'saved_character': disk['character'],
            'memory_changed_before_stale_refusal': before != after,
            'callback_saved_update_preserved': disk == seen['saved_after_callback'],
            'next_operation': outcome(lambda: dwell(s)),
            'reload_and_audit': outcome(lambda: o.audit(reload(s)))}


def _pending_commit(d, install=True):
    s, o = born(d)
    r = reading(s)
    apply(s, o, r, attest=False)
    if install:
        real = o.witness.commit
        def fail(cp):
            raise OSError('injected witness commit failure, before its write')
        o.witness.commit = fail
    else:
        real = s.install_checkpoint
        def fail(*args):
            raise OSError('injected interruption before checkpoint install')
        s.install_checkpoint = fail
    try:
        first = outcome(lambda: o.attest(s))
    finally:
        if install: o.witness.commit = real
        else: s.install_checkpoint = real
    require_exception(first, 'OSError')
    assert intent_pending(o, s)
    return s, o, first


def _pending_tail(d):
    s, o, first = _pending_commit(d)
    initial = {'head': witness_seq(o, s), 'saved_checkpoint': saved(s)['checkpoint']['sequence'],
               'pending': intent_pending(o, s)}
    r = reading(s, 'formality')
    applied = apply(s, o, r, attest=False)
    blocked = {
        'reload': outcome(lambda: reload(s)),
        'attest_same_object': outcome(lambda: o.attest(s)),
        'audit_same_object': outcome(lambda: o.audit(s)),
        'restore_same_object': outcome(lambda: o.restore(s)),
        'restore_new_unloaded_object': outcome(lambda: reopen_owner(o).restore(K.HumbleSeed(s.data_dir))),
        'attest_fresh_owner': outcome(lambda: reopen_owner(o).attest(s))}
    require_exception(blocked['reload'], 'IntegrityError')
    for key in blocked:
        if key != 'reload': require_exception(blocked[key], 'RollbackDetected')
    assert witness_seq(o, s) == 0 and saved(s)['checkpoint']['sequence'] == 1 and intent_pending(o, s)
    return {'run': 'interrupt witness commit after checkpoint install; apply another signed crossing; try recovery and restore',
            'interruption': first, 'before_second_crossing': initial,
            'second_crossing': applied['status'], 'recovery_attempts': blocked,
            'head_after': witness_seq(o, s), 'pending_after': intent_pending(o, s),
            'note': 'No file corruption or candidate edit. Recovery validates the entire saved tail, so the valid pending checkpoint cannot complete before that tail is attested or discarded; both routes recover first.'}


def _late_signal(d, restoring=False):
    """Real same-thread POSIX signal, deterministically scheduled by a Python line trace.
    No lock, generation check, serializer, filesystem function, or candidate method is replaced.
    The handler calls only public operations. It runs once after _save's CAS/snapshot,
    immediately before _durable_write, a valid Python signal delivery point.
    """
    s, o = born(d)
    if restoring:
        # A throwaway test key, kept only inside this check's temporary fixture.
        (d/'owner_key.pem').write_text(o._pem)
        dwell(s)
        target = K.HumbleSeed(s.data_dir)
    else:
        other = reload(s)
        target = s
    observed = {'delivered': False, 'restoring': restoring}
    def handler(signum, frame):
        observed['handler_lock_owned'] = lock_owned(s)
        if restoring:
            assert o.attest(s) is True
            observed['nested_checkpoint'] = saved(s)['checkpoint']
            observed['nested_witness'] = witness_seq(o, s)
            observed['nested_signature'] = saved(s)['checkpoint_sig']
            observed['nested_checkpoint_hash'] = K.OwnerWitness._checkpoint_hash(s.checkpoint)
            observed['nested_witness_hash'] = K.OwnerWitness(o.witness.path).head_for(s.organism_id)['checkpoint_hash']
            assert observed['nested_checkpoint_hash'] == observed['nested_witness_hash']
            observed['nested_signed_state_verified'] = reload(s).verify()
        else:
            dwell(other, 'curiosity')
            observed['nested_saved_event'] = other.trace[-1]['entry_hash']
        observed['nested_saved_generation'] = saved(s)['generation']
    source = CAND.read_text().splitlines()
    old_handler, old_trace = signal.getsignal(signal.SIGUSR1), sys.gettrace()
    def trace(frame, event, arg):
        if (event == 'line' and frame.f_code.co_filename == str(CAND)
            and frame.f_code.co_name == '_save' and not observed['delivered']
            and '_durable_write(self._state_path(), text)' in source[frame.f_lineno-1]
            and ((restoring and frame.f_locals['self'] is not s) or
                 (not restoring and frame.f_locals['self'] is s))):
            observed['delivered'] = True
            observed['delivery_line'] = frame.f_lineno
            observed['generation_at_snapshot'] = frame.f_locals['saved']
            signal.raise_signal(signal.SIGUSR1)
        return trace
    signal.signal(signal.SIGUSR1, handler)
    try:
        sys.settrace(trace)
        outer = outcome(lambda: o.restore(target)) if restoring else outcome(lambda: dwell(s, 'formality'))
    finally:
        sys.settrace(old_trace)
        signal.signal(signal.SIGUSR1, old_handler)
    assert observed['delivered'] and observed['handler_lock_owned'] and 'returned' in outer, (observed, outer)
    disk = saved(s)
    observed.update(outer_result=outer, final_generation=disk['generation'],
                    final_checkpoint=disk['checkpoint']['sequence'], final_witness=witness_seq(o, s))
    if restoring:
        assert observed['nested_witness'] == 1 and observed['final_witness'] == 1
        assert disk['checkpoint']['sequence'] == 0
        fresh = reload(s)
        observed['post_restore_attempts'] = {
            'audit': outcome(lambda: o.audit(fresh)),
            'attest': outcome(lambda: o.attest(fresh)),
            'restore': outcome(lambda: o.restore(fresh))}
        for r in observed['post_restore_attempts'].values(): require_exception(r, 'RollbackDetected')
        observed['pending_after'] = intent_pending(o, s)
        assert not observed['pending_after']
        observed['signed_checkpoint_discarded'] = True
    else:
        observed['nested_saved_event_still_on_disk'] = any(e['entry_hash'] == observed['nested_saved_event'] for e in disk['trace'])
        assert not observed['nested_saved_event_still_on_disk']
        assert disk['generation'] == observed['nested_saved_generation']
        observed['reload_and_audit'] = outcome(lambda: o.audit(reload(s)))
        assert observed['reload_and_audit'].get('returned') is True
    observed['scheduling'] = 'sys.settrace delivers one real SIGUSR1 immediately before _durable_write; handler performs a nested public operation in the same thread'
    return observed


def _uncertain_install(d, interrupt=False):
    s, o = born(d)
    real_fsync, real_gen = K.os.fsync, s._saved_generation
    before = memory(s)
    fired = {'fsync': False, 'reread': False}
    def fsync(fd):
        if not fired['fsync'] and stat.S_ISDIR(os.fstat(fd).st_mode) and saved(s)['checkpoint']['sequence'] == 1:
            fired['fsync'] = True
            raise OSError('injected directory fsync failure after replace')
        return real_fsync(fd)
    def gen():
        if fired['fsync'] and not fired['reread']:
            fired['reread'] = True
            if interrupt: raise KeyboardInterrupt('injected interruption during generation reread')
            raise OSError('injected unreadable generation reread')
        return real_gen()
    K.os.fsync, s._saved_generation = fsync, gen
    try:
        first = capture(lambda: o.attest(s))
    finally:
        K.os.fsync = real_fsync
        del s._saved_generation
    assert all(fired.values())
    return s, o, {'injected': fired, 'attest': first, 'before_checkpoint': before['checkpoint']['sequence'],
                  'memory_checkpoint': s.checkpoint.sequence, 'disk_checkpoint': saved(s)['checkpoint']['sequence'],
                  'memory_generation': s._generation, 'disk_generation': saved(s)['generation']}


def check_Q1(d):
    # Dynamic line/call tracing confirms actual lock ownership in all six bodies.
    methods = {'hatch','_load_locked','dwell_or_propose','record_owner_answer','authorize_and_apply','install_checkpoint'}
    observations, phase = {}, {'name': ''}
    def tracer(frame, event, arg):
        if event == 'call' and frame.f_code.co_filename == str(CAND):
            obj = frame.f_locals.get('self')
            name = frame.f_code.co_name
            if isinstance(obj, K.HumbleSeed) and (name in methods or name == '_check_current'):
                observations.setdefault(phase['name'], []).append({'method': name, 'lock_owned': lock_owned(obj)})
        return tracer
    old = sys.gettrace()
    try:
        sys.settrace(tracer)
        phase['name'] = 'hatch_and_genesis_install'; s, o = born(d)
        phase['name'] = 'load'; f = reload(s)
        phase['name'] = 'propose'; r = reading(s)
        phase['name'] = 'answer'; o.answer(s, r['proposal_id'], 'yes')
        phase['name'] = 'apply'; apply(s, o, r, attest=False)
        phase['name'] = 'install'; assert o.attest(s)
        phase['name'] = 'refresh_stale_load'; before = memory(f); f.load(); after = memory(f)
    finally:
        sys.settrace(old)
    assert all(x['lock_owned'] for items in observations.values() for x in items)
    assert not any(x['method']=='_check_current' for x in observations['load'])
    assert before != after
    return answer('HOLDS WITH CAVEATS', run='trace all six public operation bodies plus _check_current while exercising them',
                  observations=observations, stale_load_changed_memory=before != after,
                  caveat='load is a refresh: it holds the lock but performs no currency check and replaces a stale object rather than refusing it. Mutating operation entry checks were observed under lock.')


def check_Q2(d):
    s, o = born(d)
    seen = []
    real_gen, real_seal, real_write = s._saved_generation, s._compute_seal, K._durable_write
    def gen():
        seen.append({'stage':'generation_check','lock_owned':lock_owned(s)})
        return real_gen()
    def seal():
        seen.append({'stage':'snapshot_seal','lock_owned':lock_owned(s)})
        return real_seal()
    def write(path,text):
        if path == s._state_path():
            seen.append({'stage':'serialized_snapshot_and_generation','lock_owned':lock_owned(s),
                         'disk_generation_before': saved(s)['generation'], 'new_generation':json.loads(text)['generation']})
        return real_write(path,text)
    s._saved_generation, s._compute_seal, K._durable_write = gen, seal, write
    try:
        s._save()  # Direct private save, independently of an outer public operation's lock.
    finally:
        del s._saved_generation; del s._compute_seal; K._durable_write = real_write
    assert seen and all(x['lock_owned'] for x in seen)
    assert seen[-1]['new_generation'] == seen[-1]['disk_generation_before']+1
    return answer('HOLDS', run='instrument generation read, snapshot seal and serialized write during a direct _save()', stages=seen,
                  scope='Lock ownership observed. This does not imply protection against same-thread reentry; R31b tests that separately.')


def check_Q3(d):
    return answer('WRONG', **_callback_write(d), reason='The object becomes stale inside its reader; it changes character, gates, consumed IDs and trace before _save raises StaleOrganism. Disk is protected in this reader scenario.')


def _lock_wait_case(d, operation):
    s, o = born(d)
    r = reading(s)
    started, finished = threading.Event(), threading.Event()
    box = {}
    actions = {'answer':lambda:o.answer(s,r['proposal_id'],'yes'), 'attest':lambda:o.attest(s),
               'audit':lambda:o.audit(s), 'restore':lambda:o.restore(s)}
    def worker():
        started.set(); box['result'] = outcome(actions[operation]); finished.set()
    with s._organism_lock():
        th = threading.Thread(target=worker,daemon=True); th.start()
        assert started.wait(2)
        blocked = not finished.wait(.15)
    th.join(3)
    assert blocked and not th.is_alive() and 'returned' in box['result'], box
    return {'blocked_while_organism_lock_held':blocked,'completed_after_release':not th.is_alive(), 'result':box['result']}


def check_Q4(d):
    cases = {op:_lock_wait_case(d/op,op) for op in ['answer','attest','audit','restore']}
    return answer('HOLDS', run='hold organism lock in main thread; attempt each owner operation in another thread; release and join with timeouts', cases=cases)


def check_Q5(d):
    return answer('HOLDS', **_callback_write(d), scope='The generation check catches the callback write and preserves disk, after the outer operation has changed its own memory.')


def check_U1(d):
    s, o, ev = _uncertain_install(d)
    assert s._generation == K._UNUSABLE
    cp = s.checkpoint_request(); sig = K.owner_sign_external(o._pem, s.checkpoint_payload(cp))
    operations = {
        'dwell':lambda:dwell(s), 'record_owner_answer':lambda:s.record_owner_answer('missing','yes'),
        'authorize_and_apply':lambda:s.authorize_and_apply('missing',''),
        'install_checkpoint':lambda:s.install_checkpoint(cp,sig), 'hatch':lambda:s.hatch(),
        'owner_answer':lambda:o.answer(s,'missing','yes'), 'attest':lambda:o.attest(s),
        '_save':lambda:s._save()}
    refused = {name:outcome(fn) for name,fn in operations.items()}
    for x in refused.values(): require_exception(x,'StaleOrganism')
    audit = outcome(lambda:o.audit(s))
    assert audit.get('returned') is True and s._generation == K._UNUSABLE
    read_only = {'verify':outcome(lambda:s.verify()), 'checkpoint_request':{'sequence':s.checkpoint_request().sequence}}
    reload_result = outcome(lambda:s.load())
    recovered = outcome(lambda:dwell(s))
    assert 'returned' in reload_result and 'returned' in recovered
    return answer('HOLDS WITH CAVEATS', **ev, refused_operations=refused,
                  audit_without_reload=audit, read_only_without_reload=read_only,
                  explicit_load=reload_result, dwell_after_load=recovered,
                  caveat='State-mutating seed operations and attest refuse; audit and read-only methods still work on the unusable object. load is the explicit recovery exception.')


def check_U2(d):
    s, o, ordinary = _uncertain_install(d/'oserror')
    assert ordinary['memory_checkpoint'] == ordinary['disk_checkpoint'] == 1 and s._generation == -1
    s2, o2, interrupted = _uncertain_install(d/'interrupt',interrupt=True)
    require_exception(interrupted['attest'],'KeyboardInterrupt')
    assert interrupted['memory_checkpoint'] == 0 and interrupted['disk_checkpoint'] == 1
    return answer('WRONG', run='fail directory fsync after replace; interrupt the generation reread with KeyboardInterrupt',
                  ordinary_oserror_control=ordinary, interruption_counterexample=interrupted,
                  reason='The reread catches Exception, not BaseException; the interrupt escapes with the old generation, so install_checkpoint rolls memory back while the replacement checkpoint is already on disk.')


def check_G1(d):
    cases = {}
    for i,value in enumerate(['MISSING',None,True,-1,1.5,'3']):
        s,o = born(d/str(i)); raw = saved(s)
        if value == 'MISSING': raw.pop('generation')
        else: raw['generation']=value
        s._state_path().write_text(json.dumps(raw))
        before = s._state_path().read_bytes()
        f = K.HumbleSeed(s.data_dir); initial = memory(f)
        checks = {'dwell':outcome(lambda:dwell(s)), '_save':outcome(lambda:s._save()),
                  'new_hatch':outcome(lambda:f.hatch()), 'restore':outcome(lambda:o.restore(s))}
        for key in ['dwell','_save','new_hatch']: require_exception(checks[key],'StaleOrganism')
        require_exception(checks['restore'],'IntegrityError')
        assert before == s._state_path().read_bytes() and memory(f) == initial
        cases[repr(value)]={'results':checks,'file_unchanged':True,'hatch_memory_unchanged':True}
    return answer('HOLDS', run='remove or invalidate saved generation; try ordinary save, direct save, new hatch, restore',cases=cases)


def _stale_answer(d):
    s,o = born(d); r=reading(s); stale=reload(s); dwell(s)
    before_mem=memory(stale); before_disk=s._state_path().read_bytes()
    ledger_before=o.ledger.path.read_bytes() if o.ledger.path.exists() else None
    result=outcome(lambda:o.answer(stale,r['proposal_id'],'no','stale answer'))
    direct=outcome(lambda:stale.record_owner_answer(r['proposal_id'],'no','direct stale answer'))
    require_exception(result,'StaleOrganism'); require_exception(direct,'StaleOrganism')
    after_ledger=o.ledger.path.read_bytes() if o.ledger.path.exists() else None
    assert 'not recorded anywhere' in result['message']
    assert before_mem==memory(stale) and before_disk==s._state_path().read_bytes() and ledger_before==after_ledger
    return {'owner_answer':result,'direct_seed_answer':direct,'memory_unchanged':True,
            'saved_file_unchanged':True,'owner_ledger_unchanged':True}


def check_A1(d):
    return answer('HOLDS',run='load second object, advance first, answer through stale second object',**_stale_answer(d))


def _normal_restore(d):
    s,o=born(d)
    apply(s,o,reading(s))
    at_head=copy.deepcopy(s.character); cp=copy.deepcopy(K.asdict(s.checkpoint))
    dwell(s); reading(s,'curiosity')
    apply(s,o,reading(s,'formality'),attest=False)
    raw=s._state_path().read_bytes(); before=saved(s); witness_before=o.witness.path.read_bytes()
    f=K.HumbleSeed(s.data_dir)
    restored=o.restore(f)
    after=saved(f)
    keep=f.data_dir/restored['kept_as']
    assert f.character==at_head and not f.pending
    assert after['basin']==before['basin'] and keep.read_bytes()==raw
    assert K.asdict(f.checkpoint)==cp and o.witness.path.read_bytes()==witness_before
    assert f.trace[-1]['event']=='restored' and 'restored' in K.NON_AUTHORIZING_EVENTS
    assert f.trace[:cp['attested_trace_len']]==before['trace'][:cp['attested_trace_len']]
    assert o.audit(f) is True
    assert o.attest(f) is True
    return {'restored':restored,'restored_character':at_head,'pending_before':len(before['pending']),
            'pending_after':len(after['pending']),'basin_preserved':True,'discarded_file_exact_copy':True,
            'witness_unchanged_during_restore':True,'attested_prefix_preserved':True,
            'restored_event_non_authorizing':True,'audit_and_next_attest_passed':True}


def check_R1(d):
    normal=_normal_restore(d/'normal')
    s,o,first=_pending_commit(d/'pending')
    restored=o.restore(K.HumbleSeed(s.data_dir))
    assert restored['checkpoint_sequence']==1 and witness_seq(o,s)==1 and not intent_pending(o,s)
    stuck=_pending_tail(d/'pending_tail')
    return answer('HOLDS WITH CAVEATS', normal=normal, installed_pending_resolution={'interruption':first,'restore':restored},
                  unresolved_pending_with_tail=stuck,
                  caveat='Successful normal and installed-pending restore rebuild correctly. A later unattested crossing can make pending recovery block restore; verified in code, not just inferred.')


def check_R2(d):
    s,o=born(d/'normal'); dwell(s); before=witness_seq(o,s)
    o.restore(s); after=witness_seq(o,s); assert before==after==0
    s,o,first=_pending_commit(d/'pending'); before=witness_seq(o,s)
    res=o.restore(s); after=witness_seq(o,s)
    assert before==0 and after==1
    return answer('WRONG',normal_restore={'head_before':0,'head_after':0},pending_restore={'interruption':first,'head_before':before,'head_after':after,'restore':res},
                  reason='restore completes an installed pending checkpoint and advances the witness. The witness is unchanged only after recovery has resolved the pending commit.')


def check_R20(d):
    s,o=born(d/'normal'); r=reading(s); apply(s,o,r,attest=False)
    o.clock=lambda:time.time()+K.policy_ttl(s.constitution)+60
    refusal=outcome(lambda:o.attest(s)); require_exception(refusal,'AttestationRefused')
    old_sig=o.ledger.signed(s.organism_id,K._sha256(r['payload_to_sign']))
    res=o.restore(K.HumbleSeed(s.data_dir)); f=reload(s)
    assert f.character['verbosity']==.5 and not f.pending
    r2=reading(f); assert r2['proposal_id']!=r['proposal_id']
    applied=apply(f,o,r2)
    assert old_sig is not None and applied['status']=='applied'
    s2,o2,first=_pending_commit(d/'pending')
    apply(s2,o2,reading(s2,'formality'),attest=False)
    o2.clock=lambda:time.time()+K.policy_ttl(s2.constitution)+60
    blocked=outcome(lambda:o2.restore(K.HumbleSeed(s2.data_dir)))
    require_exception(blocked,'RollbackDetected')
    return answer('WRONG',normal_expiry={'attest':refusal,'restore':res,'new_reading_and_signing':'applied and attested'},
                  pending_expiry={'first_interruption':first,'restore':blocked},
                  reason='Expired-crossing recovery works with no pending commit, but an installed pending checkpoint followed by an unattested crossing blocks restore even after expiry.')


def _fail_before_landing(d,other_writes=False):
    s,o=born(d); before=saved(s); real=K._durable_write
    def fail(path,text):
        if path==s._state_path(): raise OSError('injected failure before replacement')
        return real(path,text)
    K._durable_write=fail
    try: failed=outcome(lambda:dwell(s))
    finally: K._durable_write=real
    require_exception(failed,'OSError')
    assert len(s.trace)==len(before['trace'])+1 and saved(s)==before
    unsaved_hash=s.trace[-1]['entry_hash']
    if other_writes:
        f=reload(s); dwell(f,'curiosity'); latest=s._state_path().read_bytes()
        nxt=outcome(lambda:dwell(s)); require_exception(nxt,'StaleOrganism')
        assert s._state_path().read_bytes()==latest
        fresh=reload(s); assert not any(e['entry_hash']==unsaved_hash for e in fresh.trace)
    else:
        nxt=outcome(lambda:dwell(s)); assert 'returned' in nxt
        assert any(e['entry_hash']==unsaved_hash for e in saved(s)['trace'])
        fresh=reload(s); assert o.audit(fresh)
    return {'failed_save':failed,'memory_ahead_disk_after_failure':True,'other_object_writes':other_writes,
            'next_operation':nxt,'unsaved_change_persisted':not other_writes,
            'newer_disk_unchanged_on_stale_refusal':other_writes}


def check_R31a(d):
    return answer('HOLDS',retry=_fail_before_landing(d/'retry'),stale=_fail_before_landing(d/'stale',True))


def check_R31b(d):
    return answer('WRONG',**_late_signal(d), reason='A nested public operation in a real signal handler saves an update after the outer save checks generation; outer then overwrites it using the same generation.')


def check_R33(d):
    baseline=_stale_answer(d/'entry')
    during=_callback_write(d/'during')
    return answer('HOLDS WITH CAVEATS',stale_at_entry=baseline,becomes_stale_during_reader=during,
                  caveat='An already-stale object is refused before mutation and its answer is recorded nowhere. An object that becomes stale during the reader changes memory before refusal (Q3). load also explicitly refreshes stale objects.')


def check_R35a(d):
    # Thread serialization of a whole operation, not just the save.
    s,o=born(d/'thread'); entered=threading.Event(); release=threading.Event(); finished=threading.Event(); box={}
    real=s.interpret
    def interpret(*args):
        if threading.current_thread().name=='first':
            entered.set(); assert release.wait(3)
        return real(*args)
    s.interpret=interpret
    def first(): box['first']=outcome(lambda:dwell(s))
    def second(): box['second']=outcome(lambda:dwell(s,'curiosity')); finished.set()
    a=threading.Thread(target=first,name='first',daemon=True); b=threading.Thread(target=second,daemon=True)
    a.start(); assert entered.wait(2); b.start(); blocked=not finished.wait(.15); release.set()
    a.join(3); b.join(3); del s.interpret
    assert blocked and not a.is_alive() and not b.is_alive() and all('returned' in v for v in box.values())
    assert sum(e['event']=='dwelling' for e in reload(s).trace)==2
    # A distinct process must also wait on flock. The child announces readiness before load.
    marker=d/'ready'
    code="from pathlib import Path\nprint('READY', flush=True)\ns=K.HumbleSeed(sys.argv[2]); s.load(); s.dwell_or_propose('formality','evt','hmm ok'); print('DONE',flush=True)\n"
    with s._organism_lock():
        p=python_subprocess(code,s.data_dir,wait=False)
        import select
        assert select.select([p.stdout],[],[],3)[0], 'child did not start'
        ready=p.stdout.readline().strip(); assert ready=='READY',ready
        time.sleep(.15); process_blocked=p.poll() is None
    try: out,err=p.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill(); out,err=p.communicate(); raise AssertionError('child hung after release')
    assert process_blocked and p.returncode==0 and 'DONE' in out,(out,err)
    # Serialization across distinct threads/processes does not prevent intentional reentry.
    nested=_late_signal(d/'reentry')
    return answer('HOLDS WITH CAVEATS',thread={'second_waited_for_whole_operation':blocked,'both_saved':True},
                  process={'blocked_under_flock':process_blocked,'rc':p.returncode,'stdout':out,'stderr':err},
                  same_thread_reentry=nested,
                  caveat='Threads and processes serialize in these tests. Same-thread reentrant operations can interleave, including the signal-handler counterexample; they are not serialized as whole operations.')


def check_R35b(d):
    return answer('HOLDS',**_callback_write(d),scope='This specific reader-to-another-object scenario is detected at save; the outer object still has unsaved memory changes.')


def check_R36(d):
    normal=_normal_restore(d/'normal')
    cases={}
    for name in ['unreadable','truncated','rewritten']:
        s,o=born(d/name); apply(s,o,reading(s))
        if name=='unreadable': s._state_path().write_text('{broken')
        else:
            data=saved(s)
            if name=='truncated': data['trace']=data['trace'][:s.checkpoint.attested_trace_len-1]
            else: data['trace'][0]['organism_id']='rewritten'
            s._state_path().write_text(json.dumps(data))
        before=s._state_path().read_bytes(); res=outcome(lambda:o.restore(K.HumbleSeed(s.data_dir)))
        assert res.get('exception') in ['IntegrityError','RollbackDetected'],res
        assert before==s._state_path().read_bytes() and not list(s.data_dir.glob('pre_restore*'))
        cases[name]={'restore':res,'no_state_write':True,'no_backup_created':True}
    return answer('HOLDS',normal=normal,invalid_saved_prefix=cases,
                  scope='Intact-prefix restores preserve basin and an exact discarded-file copy. On first restore, an unreadable/truncated/rewritten prefix is refused; no independent prefix backup was present.')


def check_QA(d):
    return answer('FOUND',saved_update_loss=_late_signal(d/'lost_update'),
                  pending_commit_dead_end=_pending_tail(d/'pending'),
                  scope='Concrete counterexamples, not an exhaustive concurrency proof.')


def check_QB(d):
    pending = _pending_tail(d/'pending')
    race = _late_signal(d/'restore', restoring=True)
    # Start a brand-new interpreter with only persisted files and the legitimate test
    # owner's key. No original in-memory checkpoint survives into this process.
    code = r"""
from pathlib import Path
import json
p=Path(sys.argv[2]); s=K.HumbleSeed(p/'org'); s.load()
o=K.OwnerTool((p/'owner_key.pem').read_text(),K.OwnerWitness(p/'witness.json'))
results={}
for name in ['attest','audit','restore']:
    try: results[name]={'returned':getattr(o,name)(s)}
    except Exception as e: results[name]={'exception':type(e).__name__,'message':str(e)}
print(json.dumps(results))
"""
    restart = python_subprocess(code, d/'restore', timeout=5)
    assert restart['rc']==0 and not restart['stderr'],restart
    restarted_results=json.loads(restart['stdout'])
    for x in restarted_results.values(): require_exception(x,'RollbackDetected')
    return answer('FOUND', failed_commit_then_unattested_tail=pending,
                  restore_overwrites_new_signoff=race, fresh_process_after_restore=restarted_results,
                  scope='Persisted state cannot be signed off through fresh OwnerTool.attest/audit/restore sessions in these reproductions. This is an operational dead end in those APIs, not a proof that arbitrary manual repair is impossible. No unauthorized-attestation claim is made.')


def check_QC(d):
    return answer('FOUND',**_late_signal(d,restoring=True),
                  reason='While restore saves its already-verified old-head snapshot, a real same-thread signal handler completes a new owner attestation. Restore then overwrites that signed-off checkpoint and returns the older checkpoint, leaving witness ahead and no pending intent.')


def extra_lock_inversion(d):
    # Isolated child: a reader owns organism.lock; another thread owns owner.lock;
    # the reader then calls an owner API. Both documented locks are correct locally,
    # but their ordering produces a cycle. Kill the whole child on the deadline.
    code=r'''
from pathlib import Path
import threading,time
s=K.HumbleSeed(Path(sys.argv[2])/'org'); _,pem,_=s.hatch()
o=K.OwnerTool(pem,K.OwnerWitness(Path(sys.argv[2])/'witness.json')); o.attest(s)
r=s.dwell_or_propose('verbosity','evt','I always prefer shorter answers')
sig=o.sign_proposal(r['payload_to_sign'])
reader_entered=threading.Event(); owner_entered=threading.Event()
def owner_worker():
    reader_entered.wait(2)
    with K._OwnerLock(o.lock_path):
        owner_entered.set()
        print('OWNER_LOCK_HELD_WAITING_FOR_ORGANISM',flush=True)
        o.audit(s)
def reader(*args):
    reader_entered.set()
    assert owner_entered.wait(2)
    print('READER_HOLDS_ORGANISM_WAITING_FOR_OWNER',flush=True)
    o.sign_proposal(r['payload_to_sign'])
    return None
s.reader=reader
threading.Thread(target=owner_worker,daemon=True).start()
s.authorize_and_apply(r['proposal_id'],sig)
print('FINISHED',flush=True)
'''
    p=python_subprocess(code,d,wait=False)
    try:
        out,err=p.communicate(timeout=3)
        timed_out=False
    except subprocess.TimeoutExpired:
        timed_out=True; p.kill(); out,err=p.communicate(timeout=3)
    assert timed_out and 'OWNER_LOCK_HELD_WAITING_FOR_ORGANISM' in out and 'READER_HOLDS_ORGANISM_WAITING_FOR_OWNER' in out,(out,err)
    return answer('FOUND',run='reader calls owner API while another thread is in an owner operation; child timeout 3 seconds',
                  timed_out=timed_out,stdout=out,stderr=err,
                  reason='Owner APIs acquire owner then organism; the reader already holds organism and requests owner. This is a live-lock-order deadlock; the child was terminated, not left running.')


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
CLAIM_VERDICTS = {"HOLDS", "HOLDS WITH CAVEATS", "WRONG", "NOT TESTED"}
QUESTION_VERDICTS = {"FOUND", "NOT FOUND", "NOT TESTED"}


def _run_inline(fn):
    with tempfile.TemporaryDirectory(prefix="hs087_claims_") as t:
        d = Path(t) / "case"
        d.mkdir()
        t0 = time.time()
        try:
            r = fn(d)
        except Exception as e:
            r = {"verdict": "ERROR", "evidence": f"{type(e).__name__}: {e}",
                 "traceback": traceback.format_exc()[-2000:]}
        r["seconds"] = round(time.time() - t0, 2)
        return r



def _run(fn):
    """Isolate every check in a process; bound hangs without disabling real signal tests."""
    started = time.monotonic()
    try:
        p = subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                            '--one-check', fn.__name__], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as e:
        return {'verdict': 'ERROR', 'evidence': 'check exceeded 30-second deadline; child terminated',
                'seconds': round(time.monotonic()-started, 2)}
    if p.returncode != 0:
        return {'verdict': 'ERROR', 'evidence': {'check_exit_code':p.returncode,
                'stdout':p.stdout, 'stderr':p.stderr}, 'seconds':round(time.monotonic()-started,2)}
    try:
        result = json.loads(p.stdout)
    except ValueError:
        return {'verdict': 'ERROR', 'evidence': {'non_json_stdout':p.stdout, 'stderr':p.stderr}}
    result['check_process_exit_code'] = p.returncode
    if p.stderr: result['check_stderr'] = p.stderr
    return result


def main():
    results = {"python": sys.version.split()[0], "candidate": CAND.name, "claims": {}, "open_questions": {}, "extra": {}}
    try:
        import cryptography
        results["cryptography"] = cryptography.__version__
    except Exception:
        pass
    rows = []
    for section, items, allowed in (("claims", CLAIMS["claims"], CLAIM_VERDICTS),
                                    ("open_questions", CLAIMS["open_questions"], QUESTION_VERDICTS)):
        for c in items:
            fn = globals().get(f"check_{c['id']}")
            r = _run(fn) if fn else {"verdict": "ERROR", "evidence": f"no check_{c['id']} defined"}
            if r.get("verdict") not in allowed | {"ERROR"}:
                r["verdict_not_in_allowed_set"] = r.get("verdict")
            r["claim"] = c["text"]
            results[section][c["id"]] = r
            rows.append((c["id"], r.get("verdict")))
    for name in sorted(n for n in globals() if n.startswith("extra_") and callable(globals()[n])):
        r = _run(globals()[name])
        results["extra"][name] = r
        rows.append((name, r.get("verdict")))
    out = HERE / "CLAIMS_RESULTS_v0_8_7.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True, default=repr))
    print(f"Humble Seed v0.8.7 claims battery  (Python {results['python']}, cryptography {results.get('cryptography')})")
    for cid, v in rows:
        print(f"  {cid:<28} {v}")
    print(f"written {out.name}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == '--one-check':
        print(json.dumps(_run_inline(globals()[sys.argv[2]]), default=repr))
    else:
        main()
