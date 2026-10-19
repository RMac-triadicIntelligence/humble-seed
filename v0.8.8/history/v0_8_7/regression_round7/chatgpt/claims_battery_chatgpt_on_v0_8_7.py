#!/usr/bin/env python3
"""Claims battery for Humble Seed v0.8.6: a scaffold for checking whether each documented claim
in the candidate's docstring is accurate as stated.

The claims are in CLAIMS.json, quoted verbatim from the docstring. For each claim there is one
check_<ID>(d) function below. Fill it in, so that it returns:
    {"verdict": "HOLDS" | "HOLDS WITH CAVEATS" | "WRONG" | "NOT TESTED",
     "evidence": <anything JSON-serializable: what you ran and what it returned>}
Open questions Q1 and Q2 have check_Q1 and check_Q2; a "verdict" there is "FOUND" or "NOT FOUND".
Anything else you find goes in a function named extra_<name>(d); it is run and reported too.

Each function gets a fresh, empty temporary directory d (a pathlib.Path).
Run:  python3 -I claims_battery_v0_8_6.py
Output: a table on stdout, and CLAIMS_RESULTS_on_v0_8_7.json next to this file.
"""
import importlib.util, json, os, stat, subprocess, sys, tempfile, threading, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAND = HERE.parent.parent / "humble_seed_v0_8_7_candidate.py"
CLAIMS = json.loads((HERE / "CLAIMS.json").read_text())


def _load(path, alias):
    spec = importlib.util.spec_from_file_location(alias, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m          # needed: the candidate defines dataclasses
    spec.loader.exec_module(m)
    return m


K = _load(CAND, "hs086")

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
          "spec = importlib.util.spec_from_file_location('hs086', sys.argv[1])\n"
          "K = importlib.util.module_from_spec(spec); sys.modules['hs086'] = K; spec.loader.exec_module(K)\n")


def python_subprocess(code, *args, timeout=300, wait=True):
    """Run `LOADER + code` in a separate Python process. Inside it, K is the candidate and
    sys.argv[2:] are *args (as strings). With wait=False, returns the Popen object."""
    cmd = [sys.executable, "-I", "-c", LOADER + code, str(CAND), *map(str, args)]
    if not wait:
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {"rc": p.returncode, "stdout": p.stdout[-4000:], "stderr": p.stderr[-4000:]}


NOT_TESTED = {"verdict": "NOT TESTED", "evidence": None}


# ---------------------------------------------------------------------------
# Worked example
# ---------------------------------------------------------------------------

def check_O1(d):
    """The saved state carries a generation number. (Example: checked here for hatch, attest, dwell.)"""
    seed = K.HumbleSeed(d / "org")
    _, pem, _ = seed.hatch()
    gens = [saved(seed).get("generation")]
    owner = K.OwnerTool(pem, K.OwnerWitness(d / "witness.json"))
    owner.attest(seed)
    gens.append(saved(seed).get("generation"))
    for _ in range(3):
        dwell(seed)
        gens.append(saved(seed).get("generation"))
    ints = all(isinstance(g, int) and not isinstance(g, bool) for g in gens)
    steps = [b - a for a, b in zip(gens, gens[1:])] if ints else None
    verdict = "HOLDS" if ints and steps == [1] * len(steps) else "WRONG"
    return {"verdict": verdict, "evidence": {"generations_after_each_save": gens, "steps": steps}}


# ---------------------------------------------------------------------------
# Claims to check (texts from CLAIMS.json). Replace `return NOT_TESTED`.
# ---------------------------------------------------------------------------


# Independent checks added by ChatGPT, 2026-10-19. Candidate bytes are unchanged.
# Faults are scoped and restored, and all synchronization uses bounded events.
from contextlib import contextmanager
import hashlib

@contextmanager
def patched(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield old
    finally:
        setattr(obj, name, old)


def result(verdict, **evidence):
    return {"verdict": verdict, "evidence": evidence}


def raises_as(r, name):
    assert r.get("exception") == name, r


def fail_write(*args, **kwargs):
    raise OSError("injected failure before replace")


def disk_memory(seed):
    st = saved(seed)
    return {"memory_generation": seed._generation, "disk_generation": st["generation"],
            "memory_checkpoint": seed.checkpoint.sequence if seed.checkpoint else None,
            "disk_checkpoint": st["checkpoint"]["sequence"] if st["checkpoint"] else None,
            "memory_trace_len": len(seed.trace), "disk_trace_len": len(st["trace"]),
            "memory_basin_len": len(seed.basin), "disk_basin_len": len(st["basin"]),
            "memory_character": dict(seed.character), "disk_character": st["character"]}


def flock_probe(path):
    r = python_subprocess("""
import fcntl, os
fd=os.open(sys.argv[2],os.O_CREAT|os.O_RDWR,0o600)
try:
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    print('ACQUIRED')
except BlockingIOError:
    print('BLOCKED')
finally:
    os.close(fd)
""", path, timeout=15)
    assert r["rc"] == 0, r
    return r["stdout"].strip()


def make_pending(d, installed):
    seed, owner = born(d)
    dwell(seed)
    before = seed._state_path().read_bytes()
    if installed:
        with patched(owner.witness, "commit", fail_write):
            err = outcome(lambda: owner.attest(seed))
    else:
        with patched(seed, "install_checkpoint", fail_write):
            err = outcome(lambda: owner.attest(seed))
    raises_as(err, "OSError")
    assert intent_pending(owner, seed)
    return seed, owner, before, err


def check_O2(d):
    seed, owner = born(d)
    observed=[]
    write=K._durable_write
    def probe(path,text):
        if Path(path)==seed._state_path():
            observed.append(flock_probe(seed.data_dir/'organism.lock'))
        return write(path,text)
    with seed._organism_lock():
        with seed._organism_lock():
            nested=flock_probe(seed.data_dir/'organism.lock')
    with patched(K,'_durable_write',probe):
        dwell(seed); reading(seed); owner.attest(seed)
    assert observed and set(observed)=={'BLOCKED'} and nested=='BLOCKED'
    return result('HOLDS', ran='cross-process nonblocking flock during dwell/proposal/checkpoint writes; nested same-thread lock',
                  observed_at_state_writes=observed,nested_lock=nested,
                  scope='The actual write is locked. Snapshot construction precedes the lock; see Q1.')


def check_O3(d):
    a,owner=born(d); b=reload(a)
    dwell(a); before=a._state_path().read_bytes()
    err=outcome(lambda:dwell(b))
    raises_as(err,'StaleOrganism'); assert before==a._state_path().read_bytes()
    b.load(); dwell(b)
    return result('HOLDS', ran='two separately loaded objects: advance A, try B, reload B, retry',
                  stale_write=err, disk_unchanged_on_refusal=True,reload_and_retry=disk_memory(b),
                  scope='Equality check holds for these objects; it does not bind the generation to the serialized snapshot (Q1).')


def check_O4(d):
    a,owner=born(d); before=a._state_path().read_bytes()
    b=K.HumbleSeed(a.data_dir); err=outcome(b.hatch)
    raises_as(err,'StaleOrganism'); assert before==a._state_path().read_bytes()
    return result('HOLDS',ran='hatch a fresh object in an already populated organism directory',hatch=err,existing_bytes_preserved=True)


def check_O5(d):
    seed,owner=born(d); events=[]
    from contextlib import ExitStack
    def wrap(obj,name):
        original=getattr(obj,name)
        def call(*args,**kwargs):
            events.append({'stage':name,'other_process':flock_probe(seed.data_dir/'organism.lock')})
            return original(*args,**kwargs)
        return call
    with ExitStack() as stack:
        for obj,name in [(owner,'_recover'),(K,'owner_sign_external'),(owner.witness,'begin'),(seed,'install_checkpoint'),(owner.witness,'commit')]:
            stack.enter_context(patched(obj,name,wrap(obj,name)))
        assert owner.attest(seed)
    assert all(e['other_process']=='BLOCKED' for e in events)
    return result('HOLDS',ran='probe organism flock from another process at recovery, signing, intent, install, and witness commit',stages=events)


def check_O6(d):
    a,owner=born(d); b=reload(a); dwell(a); calls=[]
    sign=K.owner_sign_external
    def spy(*args):
        calls.append('signed'); return sign(*args)
    with patched(K,'owner_sign_external',spy):
        err=outcome(lambda:owner.attest(b))
    raises_as(err,'StaleOrganism'); assert not calls
    return result('HOLDS',ran='advance A then attest separately loaded stale B, count signing calls',attest=err,signing_calls=len(calls))


def check_I1(d):
    seed,owner=born(d); read=seed._saved_generation; calls=[]; fsync=K.os.fsync
    def reread():
        v=read(); calls.append(v); return v
    def fail_dir(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError('injected directory fsync failure after replace')
        return fsync(fd)
    before=seed._generation
    with patched(seed,'_saved_generation',reread),patched(K.os,'fsync',fail_dir):
        err=outcome(lambda:dwell(seed))
    raises_as(err,'OSError')
    assert calls==[before,before+1] and seed._generation==saved(seed)['generation']==before+1
    assert reload(seed).verify()
    return result('HOLDS',ran='raise from actual directory fsync after os.replace; spy saved-generation reads',save=err,generation_reads=calls,after=disk_memory(seed),reload_verifies=True)


def check_I2(d):
    seed,owner=born(d); read=seed._saved_generation; count=0; fsync=K.os.fsync
    def fail_dir(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError('injected post-replace directory fsync failure')
        return fsync(fd)
    def reread():
        nonlocal count
        count+=1
        # attest._require_current = 1; _save CAS = 2; post-failure reread = 3.
        if count==3:
            raise OSError('injected transient read I/O failure after replace')
        return read()
    with patched(seed,'_saved_generation',reread),patched(K.os,'fsync',fail_dir):
        # Fail only the organism fsync, not witness.begin's earlier directory fsync.
        write=K._durable_write
        def targeted(path,text):
            if Path(path)==seed._state_path(): return write(path,text)
            with patched(K.os,'fsync',fsync): return write(path,text)
        with patched(K,'_durable_write',targeted):
            err=outcome(lambda:owner.attest(seed))
    raises_as(err,'OSError')
    state=disk_memory(seed)
    assert state['memory_checkpoint']!=state['disk_checkpoint']
    assert reload(seed).verify()
    return result('WRONG',ran='checkpoint save: replace lands; directory fsync fails; generation reread also raises OSError',
                  failure=err,generation_read_calls=count,after=state,disk_loads_and_verifies=True,
                  contradiction='install rolls memory back because generation was not updated, although the new checkpoint is already on disk')


def check_C1(d):
    seed,owner,before,err=make_pending(d,True)
    pre={'pending':intent_pending(owner,seed),'witness':witness_seq(owner,seed),'saved':saved(seed)['checkpoint']['sequence'],'loads':reload(seed).verify()}
    recovered=owner._recover(seed)
    assert recovered=='completed' and not intent_pending(owner,seed)
    return result('HOLDS',ran='interrupt witness commit after checkpoint install, reload saved file, recover',interruption=err,before_recovery=pre,recovery=recovered,witness_after=witness_seq(owner,seed))


def check_C2(d):
    seed,owner,before,err=make_pending(d,True)
    st=saved(seed); st['state_seal']='0'*64; seed._state_path().write_text(json.dumps(st))
    seq=witness_seq(owner,seed); recovered=outcome(lambda:owner._recover(seed))
    raises_as(recovered,'RollbackDetected'); assert intent_pending(owner,seed) and witness_seq(owner,seed)==seq
    return result('HOLDS',ran='installed pending checkpoint, corrupt only saved integrity seal, recover',recovery=recovered,pending_retained=True,witness_not_advanced=True)


def check_C3(d):
    seed,owner,before,err=make_pending(d,False)
    st=saved(seed); st['checkpoint']['timestamp']+=1; seed._state_path().write_text(json.dumps(st))
    refused=outcome(lambda:owner._recover(seed)); raises_as(refused,'RollbackDetected')
    assert intent_pending(owner,seed)
    seed._state_path().write_bytes(before); recovered=owner._recover(seed)
    assert recovered=='abandoned' and not intent_pending(owner,seed)
    return result('HOLDS',ran='pre-install pending intent: saved checkpoint different from witness head, then restore exact witness head',off_head=refused,pending_retained_off_head=True,at_head=recovered)


def check_M1(d):
    seed,owner=born(d); spare=reading(seed); first=reading(seed); apply(seed,owner,first)
    owner.answer(seed,spare['proposal_id'],'no')
    second=reading(seed); apply(seed,owner,second,attest=False)
    err=outcome(lambda:owner.attest(seed)); raises_as(err,'AttestationRefused')
    assert "since it signed the previous verbosity crossing is 'no'" in err['message']
    return result('HOLDS',ran='after first attestation answer an older pending reading no; issue/apply next reading after the no; request attestation',attest=err,
                  distinction='organism issuance window excludes that earlier no; owner signature window includes it')


def check_R30a(d):
    # Run both recovery branches and the invalid-install guard as real code.
    return result('HOLDS',ran='three isolated recovery cases',
                  valid_install=check_C1(d/'valid')['evidence'],
                  invalid_install=check_C2(d/'invalid')['evidence'],
                  abandon_requires_head=check_C3(d/'head')['evidence'])


def check_R30b(d):
    seed,owner=born(d); st=saved(seed); st['generation']+=10
    seed._state_path().write_text(json.dumps(st)); fresh=reload(seed)
    assert fresh._generation==st['generation'] and fresh.verify()
    return result('HOLDS',ran='write generation directly with Path.write_text, reload and verify',written_generation=st['generation'],loaded_generation=fresh._generation,verify=True,
                  note='generation is not included in the seal; no security bypass is inferred merely from a direct edit')


def check_R30c(d):
    seed,owner,before,err=make_pending(d,True); seq=witness_seq(owner,seed)
    seed._state_path().write_bytes(before); recovered=owner._recover(seed)
    assert recovered=='abandoned' and witness_seq(owner,seed)==seq and not intent_pending(owner,seed)
    return result('HOLDS',ran='interrupt after install, restore byte-exact pre-install file, recover',install_interruption=err,recovery=recovered,witness_sequence=seq,restored_file_verifies=reload(seed).verify())


def check_R31a(d):
    seed,owner=born(d); before=disk_memory(seed)
    with patched(K,'_durable_write',fail_write):
        dwell_error=outcome(lambda:dwell(seed))
    raises_as(dwell_error,'OSError'); after_dwell=disk_memory(seed)
    assert after_dwell['memory_trace_len']>after_dwell['disk_trace_len']
    # Save the nontransactional dwell, then fail checkpoint install itself.
    seed._save(); before_install=disk_memory(seed)
    write=K._durable_write
    def targeted(path,text):
        if Path(path)==seed._state_path(): return fail_write()
        return write(path,text)
    with patched(K,'_durable_write',targeted):
        install_error=outcome(lambda:owner.attest(seed))
    raises_as(install_error,'OSError'); after_install=disk_memory(seed)
    assert after_install==before_install
    return result('HOLDS WITH CAVEATS',ran='fail ordinary dwell save, then fail only the checkpoint state write before replace',
                  dwell_error=dwell_error,dwell_before=before,dwell_after=after_dwell,install_error=install_error,install_before=before_install,install_after=after_install,
                  caveat='checkpoint rollback holds for this pre-replace failure; its unconditional transactional behavior fails in I2')


def check_R31b(d):
    seed,owner=born(d)
    with patched(K,'_durable_write',fail_write): err=outcome(lambda:dwell(seed))
    raises_as(err,'OSError'); ahead=disk_memory(seed); seed._save(); after=disk_memory(seed)
    assert ahead['memory_trace_len']>ahead['disk_trace_len'] and after['memory_trace_len']==after['disk_trace_len']
    return result('HOLDS WITH CAVEATS',ran='fail dwell before replace, retry _save on the same object',failure=err,ahead=ahead,after_retry=after,
                  caveat='retry writes the unsaved state only if another object has not advanced disk in the meantime; R31c runs that counterexample')


def check_R31c(d):
    a,owner=born(d); b=reload(a)
    with patched(K,'_durable_write',fail_write): err=outcome(lambda:dwell(a,'curiosity'))
    raises_as(err,'OSError'); dwell(b,'formality')
    retry=outcome(a._save); raises_as(retry,'StaleOrganism')
    pre_reload=disk_memory(a); a.load()
    categories=[e.get('category') for e in a.trace if e['event']=='dwelling']
    assert categories==['formality']
    return result('WRONG',ran='A dwell save fails before replace; B loaded at the same generation successfully saves; A retry is stale and reload loses A update',
                  first_failure=err,A_retry=retry,before_reload=pre_reload,categories_after_reload=categories,
                  contradiction='generation check does not reserve a generation for an in-memory update whose save failed')


def check_R32a(d):
    seed,owner=born(d)
    with seed._organism_lock(): org=flock_probe(seed.data_dir/'organism.lock')
    with K._OwnerLock(owner.lock_path): own=flock_probe(owner.lock_path)
    free=flock_probe(seed.data_dir/'organism.lock')
    assert org==own=='BLOCKED' and free=='ACQUIRED'
    return result('HOLDS',ran='try POSIX flock LOCK_EX|LOCK_NB in independent processes under both locks and after release',organism=org,owner=own,after_release=free)


def check_R32b(d):
    seed,owner=born(d)
    with seed._organism_lock():
        r=python_subprocess("from pathlib import Path\np=Path(sys.argv[2]); p.write_bytes(p.read_bytes()+b'\\n'); print('DIRECT_WRITE_COMPLETED')",seed._state_path(),timeout=15)
    assert r['rc']==0 and 'DIRECT_WRITE_COMPLETED' in r['stdout']
    return result('HOLDS',ran='hold organism flock and write the state directly from another process',process=r,reload_verifies=reload(seed).verify())


def check_R33a(d):
    seed,owner=born(d); stale=reload(seed); dwell(seed,'formality')
    failed=outcome(lambda:dwell(stale,'curiosity')); raises_as(failed,'StaleOrganism')
    ahead=[e.get('category') for e in stale.trace if e['event']=='dwelling']
    stale.load(); after=[e.get('category') for e in stale.trace if e['event']=='dwelling']
    assert 'curiosity' in ahead and after==['formality']
    return result('HOLDS',ran='mutate stale object, observe save refusal, call load on that same object',save=failed,memory_before_reload=ahead,memory_after_reload=after)


def check_R33b(d):
    seed,owner=born(d); r=reading(seed); stale=reload(seed); dwell(seed)
    err=outcome(lambda:owner.answer(stale,r['proposal_id'],'no')); raises_as(err,'StaleOrganism')
    ledger=owner.ledger.answers_to(seed.organism_id,r['proposal_id'])
    mem=[e['answer'] for e in stale.trace if e['event']=='owner_answer']
    disk=[e['answer'] for e in saved(seed)['trace'] if e['event']=='owner_answer']
    assert ledger==mem==['no'] and disk==[]
    return result('HOLDS WITH CAVEATS',ran='answer no through a separately loaded stale organism',answer=err,authoritative_owner_ledger=ledger,stale_organism_memory=mem,saved_organism=disk,
                  caveat='not the organism is accurate only for persisted state: its in-memory trace and basin receive the answer before StaleOrganism is raised')


def check_R34(d):
    seed,owner=born(d); original=Path.read_text; reads=[]
    def spy(path,*args,**kwargs):
        text=original(path,*args,**kwargs)
        if path==seed._state_path(): reads.append({'bytes':len(text.encode()),'trace_entries':len(json.loads(text)['trace'])})
        return text
    with patched(Path,'read_text',spy):
        seed._save()
        for _ in range(12): dwell(seed)
        seed._save()
    assert len(reads)==14 and reads[-1]['bytes']>reads[0]['bytes']
    return result('HOLDS',ran='instrument all full-state reads during 14 saves while extending trace',reads=reads,
                  scope='existing saved states; initial hatch has no existing file to read; measured bytes parsed, not an asymptotic timing benchmark')


def check_W1(d):
    seed,owner=born(d); old=reading(seed)
    owner.answer(seed,old['proposal_id'],'no')
    r=reading(seed); sig=owner.sign_proposal(r['payload_to_sign'])
    # no predates the signature and issuance, so organism permits this crossing.
    assert seed.authorize_and_apply(r['proposal_id'],sig) is not None
    refusal=outcome(lambda:owner.attest(seed)); raises_as(refusal,'AttestationRefused')
    # A later explicit yes supersedes the category no; it does not rewrite history.
    owner.answer(seed,old['proposal_id'],'yes'); assert owner.attest(seed)
    first_seq=witness_seq(owner,seed)
    next_r=reading(seed); apply(seed,owner,next_r)
    assert witness_seq(owner,seed)==first_seq+1
    return result('HOLDS',ran='no before first signature is caught at attestation; correct it to yes, attest; next category crossing succeeds without reusing old no',
                  first_refusal=refusal,correction='later owner yes to the same old reading',first_witness=first_seq,next_witness=witness_seq(owner,seed),
                  scope='tested boundary histories; finite checks do not prove all possible histories')


def stale_snapshot_race(d, checkpoint=False):
    seed,owner=born(d); ready=threading.Event(); release=threading.Event(); errors=[]; out=[]
    canonical=K._canonical_json
    def pause_snapshot(obj):
        text=canonical(obj)
        if threading.current_thread().name=='old-snapshot' and isinstance(obj,dict) and 'state_seal' in obj:
            ready.set()
            if not release.wait(10): raise TimeoutError('release snapshot')
        return text
    def first():
        try: out.append({'thread':'A','returned':dwell(seed,'curiosity')['status']})
        except BaseException as e: errors.append(type(e).__name__+': '+str(e))
    with patched(K,'_canonical_json',pause_snapshot):
        t=threading.Thread(target=first,name='old-snapshot'); t.start()
        try:
            assert ready.wait(10), 'snapshot not reached'
            if checkpoint: assert owner.attest(seed)
            else: dwell(seed,'formality')
            landed=saved(seed)
            fresh_at_middle=reload(seed)
        finally:
            release.set(); t.join(10)
        assert not t.is_alive() and not errors,(errors,t.is_alive())
    after=saved(seed); fresh=reload(seed)
    ev={'ran':'pause thread A after serialization but before organism lock; B saves on the same object; resume A',
        'thread_A':out,'middle_generation':landed['generation'],'final_generation':after['generation'],
        'middle_dwells':[e.get('category') for e in landed['trace'] if e['event']=='dwelling'],
        'final_dwells':[e.get('category') for e in after['trace'] if e['event']=='dwelling'],
        'middle_checkpoint':landed['checkpoint']['sequence'],'final_checkpoint':after['checkpoint']['sequence'],
        'witness':witness_seq(owner,seed),'pending':intent_pending(owner,seed),
        'final_load_verifies':fresh.verify()}
    if checkpoint:
        ev['audit_from_final_disk']=outcome(lambda:reopen_owner(owner).audit(fresh))
        ev['attest_from_final_disk']=outcome(lambda:reopen_owner(owner).attest(fresh))
        raises_as(ev['audit_from_final_disk'],'RollbackDetected')
        raises_as(ev['attest_from_final_disk'],'RollbackDetected')
        assert landed['checkpoint']['sequence']>after['checkpoint']['sequence']
    else:
        assert 'formality' in ev['middle_dwells'] and 'formality' not in ev['final_dwells']
        # B's loaded object is now logically stale but equal-generation; it can write.
        ev['middle_object_write']=outcome(lambda:dwell(fresh_at_middle,'verbosity'))
        assert 'returned' in ev['middle_object_write']
        ev['dwells_after_middle_object_write']=[e.get('category') for e in saved(seed)['trace'] if e['event']=='dwelling']
    return ev


def check_Q1(d):
    return result('FOUND',same_object_threads=stale_snapshot_race(d/'lost_update'),
                  checkpoint_rewind=stale_snapshot_race(d/'checkpoint',True),
                  conclusion='a pre-lock serialized snapshot can overwrite a later successful save and checkpoint; matching the live object generation does not validate the snapshot')


def check_Q2(d):
    seed,owner=born(d); r=reading(seed); sig=owner.sign_proposal(r['payload_to_sign'])
    assert seed.authorize_and_apply(r['proposal_id'],sig) is not None
    write=K._durable_write
    def fail_install(path,text):
        if Path(path)==seed._state_path(): return fail_write()
        return write(path,text)
    with patched(K,'_durable_write',fail_install): err=outcome(lambda:owner.attest(seed))
    raises_as(err,'OSError'); assert intent_pending(owner,seed)
    load_error=outcome(lambda:reload(seed)); raises_as(load_error,'IntegrityError')
    entry=owner.ledger.signed(seed.organism_id,K._sha256(r['payload_to_sign']))
    ttl=K.policy_ttl(seed.constitution); attempts=[]
    for multiple in [2,10,100]:
        owner.clock=lambda m=multiple:entry['signed_at']+m*ttl
        refusal=outcome(lambda:owner.attest(seed)); raises_as(refusal,'AttestationRefused')
        assert 'past its lifetime' in refusal['message']; attempts.append({'ttl_multiple':multiple,**refusal})
    again=owner.sign_proposal(r['payload_to_sign']); assert again==sig
    kept=owner.ledger.signed(seed.organism_id,K._sha256(r['payload_to_sign']))
    assert kept['signed_at']==entry['signed_at']
    retry=outcome(lambda:owner.attest(seed)); raises_as(retry,'AttestationRefused')
    return result('FOUND',ran='apply and save authorized mutation; fail checkpoint state write before replace; advance owner clock past signature TTL; retry and re-sign same payload',
                  install_failure=err,reload=load_error,attestation_attempts=attempts,
                  resign_retains_first_signed_at=kept['signed_at']==entry['signed_at'],after_resign=retry,
                  pending_after_recovery=intent_pending(owner,seed),
                  interpretation='saved applied mutation remains unattested and cannot receive an attestation through this protocol under a nondecreasing owner clock; replay must keep checking the expired original signature. Repair requires restoring earlier state or a separate recovery procedure. No unauthorized sign-off found.')


def extra_checkpoint_failure_controls(d):
    rows=[]
    for stage in ['before_replace','directory_fsync']:
        seed,owner=born(d/stage)
        before=disk_memory(seed)
        write=K._durable_write; fsync=K.os.fsync
        def fail_dir(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError('injected directory fsync failure')
            return fsync(fd)
        def fault(path,text):
            if Path(path)!=seed._state_path(): return write(path,text)
            if stage=='before_replace': return fail_write()
            with patched(K.os,'fsync',fail_dir): return write(path,text)
        with patched(K,'_durable_write',fault):
            err=outcome(lambda:owner.attest(seed))
        raises_as(err,'OSError'); after=disk_memory(seed)
        assert after['memory_checkpoint']==after['disk_checkpoint']
        if stage=='before_replace': assert after==before
        else: assert after['disk_checkpoint']==before['disk_checkpoint']+1
        recovered=owner._recover(seed)
        assert recovered==('abandoned' if stage=='before_replace' else 'completed')
        assert owner.audit(seed)
        rows.append({'fault':stage,'error':err,'after':after,'recovery':recovered,'audit':True})
    # Q2 control: the same failed install can be retried before expiration.
    seed,owner=born(d/'within_ttl'); r=reading(seed); apply(seed,owner,r,attest=False)
    write=K._durable_write
    def fault(path,text):
        if Path(path)==seed._state_path(): return fail_write()
        return write(path,text)
    with patched(K,'_durable_write',fault): err=outcome(lambda:owner.attest(seed))
    raises_as(err,'OSError'); assert owner.attest(seed) and owner.audit(seed)
    return result('PASS',ran='controls distinguishing I2 double fault from ordinary single-fault handling, and Q2 expiration from a prompt retry',
                  install_single_faults=rows,retry_before_TTL={'initial_failure':err,'retry_attest':True,'audit':True})


def extra_two_objects_control(d):
    a,owner=born(d); b=reload(a); dwell(a)
    err=outcome(lambda:dwell(b)); raises_as(err,'StaleOrganism')
    return result('PASS',ran='separate-object ordinary CAS control for Q1',second_writer=err)


def extra_input_integrity(d):
    frozen=(HERE/'MANIFEST.sha256').read_text().splitlines(); rows=[]
    for line in frozen:
        expected,name=line.split(maxsplit=1); name=name.lstrip('*')
        if name in ('./claims_battery_v0_8_6.py','claims_battery_v0_8_6.py'): continue
        actual=hashlib.sha256((HERE/name).read_bytes()).hexdigest()
        rows.append({'file':name,'sha256':actual,'matches_frozen_manifest':actual==expected})
    assert all(r['matches_frozen_manifest'] for r in rows)
    return result('PASS',candidate_and_other_frozen_files=rows,
                  filled_battery_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  note='scaffold intentionally filled; every other manifest-covered file unchanged')


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
CLAIM_VERDICTS = {"HOLDS", "HOLDS WITH CAVEATS", "WRONG", "NOT TESTED"}
QUESTION_VERDICTS = {"FOUND", "NOT FOUND", "NOT TESTED"}


def _run(fn):
    with tempfile.TemporaryDirectory(prefix="hs086_claims_") as t:
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
    out = HERE / "CLAIMS_RESULTS_on_v0_8_7.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True, default=repr))
    print(f"Humble Seed v0.8.6 claims battery  (Python {results['python']}, cryptography {results.get('cryptography')})")
    for cid, v in rows:
        print(f"  {cid:<28} {v}")
    print(f"written {out.name}")


if __name__ == "__main__":
    main()
