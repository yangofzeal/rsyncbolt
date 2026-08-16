#!/usr/bin/env python3
from __future__ import print_function
import os, sys, subprocess, shutil, hashlib, json, time, shlex
BUILD='PUBLIC-LOOPBACK-LARGE-4G-V4-STEADY-TMPDIR'
BUY_URL='https://buy.stripe.com/00w14g9KP3bV8rEgblgUM07'
SIZE_MIB=4096
PATCH_BYTES=(b'RSYNCBOLT_PUBLIC_LARGE_'*4000)[:65536]
MTIME_SEC=1700000000
HOST='loopback'
BASE=os.path.join(os.environ.get('TMPDIR','/tmp'),'rsyncbolt_public_large_4g_v5')
def clock():
    f=getattr(time,'perf_counter',None); return f() if f else time.time()
def dec(x): return x if isinstance(x,str) else x.decode('utf-8','replace')
def q(s): return shlex.quote(s) if hasattr(shlex,'quote') else "'"+s.replace("'","'\\''")+"'"
def helper_for_platform():
    name='rsyncbolt_mac' if sys.platform=='darwin' else 'rsyncbolt_linux'
    dirs=[]
    env=os.environ.get('RSYNCBOLT_SIBLING_DIR')
    if env: dirs.append(os.path.abspath(os.path.expanduser(env)))
    for d in os.environ.get('PATH','').split(os.pathsep):
        if d: dirs.append(os.path.abspath(os.path.expanduser(d)))
    dirs.append(os.path.dirname(os.path.abspath('./rsyncbolt')))
    seen=set()
    for d in dirs:
        if d in seen: continue
        seen.add(d); p=os.path.join(d,name)
        if os.path.isfile(p) and os.access(p,os.X_OK): return p,name
    raise RuntimeError('%s not found on PATH'%name)
def show(label,cmd): print('%s %s'%(label,' '.join(q(x) for x in cmd))); sys.stdout.flush()
def run_raw(cmd,label=None):
    if label: show(label,cmd)
    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE); out,err=p.communicate(); return p.returncode,dec(out),dec(err)
def run(cmd,label=None):
    rc,out,err=run_raw(cmd,label)
    if rc: raise RuntimeError('FAILED rc=%d: %s\n%s%s'%(rc,' '.join(cmd),out,err))
    return out,err
def timed(cmd,label):
    show(label,cmd); t=clock(); out,err=run(cmd); return clock()-t,out,err
def make_fake_ssh(path):
    body='''#!/usr/bin/env python3\nfrom __future__ import print_function\nimport os,sys,subprocess,shlex\na=sys.argv[1:]; i=0\nwhile i<len(a) and a[i].startswith('-'):\n    if a[i] in ('-i','-o','-p','-l','-F','-S','-J') and i+1<len(a): i+=2\n    else: i+=1\nif i>=len(a): sys.exit(2)\ni+=1\ncmd=' '.join(a[i:])\ntry: parts=shlex.split(cmd)\nexcept Exception: parts=[]\nif len(parts)>=2 and parts[0].endswith('python3') and os.path.isfile(parts[1]) and os.access(parts[1],os.X_OK):\n    sys.exit(subprocess.call(parts[1:]))\nsys.exit(subprocess.call(cmd,shell=True))\n'''
    with open(path,'w') as f: f.write(body)
    os.chmod(path,0o755)
def state_path(src,dst):
    d=os.path.join(os.path.expanduser('~'),'.cache','rsyncbolt_final')
    if not os.path.isdir(d): os.makedirs(d)
    key=hashlib.sha256((os.path.abspath(src)+'\0'+HOST+'\0'+dst).encode('utf-8')).hexdigest(); return os.path.join(d,key+'.json')
def write_state(src,dst,helper,sibling,size,mtime_ns):
    p=state_path(src,dst); st={'transport':{'os':'Darwin' if sys.platform=='darwin' else 'Linux','home':os.path.expanduser('~'),'remote':helper,'root':dst,'trailing':False,'sibling':sibling,'bootstrap_kind':'binary-v1'},'files':{'large.bin':{'size':int(size),'mtime_ns':int(mtime_ns)}}}
    t=p+'.tmp'
    with open(t,'w') as f: json.dump(st,f,separators=(',',':'))
    os.replace(t,p)
def make_sparse(path,n):
    d=os.path.dirname(path)
    if d and not os.path.isdir(d): os.makedirs(d)
    with open(path,'wb') as f: f.truncate(n)
    os.utime(path,(MTIME_SEC,MTIME_SEC))
def exact(path,want_size):
    if os.path.getsize(path)!=want_size: return False
    with open(path,'rb') as f: f.seek(-len(PATCH_BYTES),os.SEEK_END); return f.read()==PATCH_BYTES
def free_gate(exe,version):
    shutil.rmtree(BASE,ignore_errors=True); os.makedirs(BASE); fake=os.path.join(BASE,'ssh_loopback'); make_fake_ssh(fake); src=os.path.join(BASE,'large.bin'); make_sparse(src,SIZE_MIB*1024*1024)
    cmd=[exe,'-pt','-e',fake,src,HOST+':'+BASE+'/free_dest/']; rc,out,err=run_raw(cmd,'RSYNCBOLT_COMMAND'); combined=out+err
    url=BUY_URL in combined; limit='Free supports files up to 2 GiB' in combined; ok=rc!=0 and url and limit
    print('RSYNCBOLT_PUBLIC_LARGE_FREE_GATE'); print('VERSION       %s'%version); print('SIZE_MIB      %d'%SIZE_MIB); print('RETURN_CODE   %d'%rc); print('BUY_URL_SEEN  %s'%('YES' if url else 'NO')); print('LIMIT_MESSAGE %s'%('YES' if limit else 'NO')); print('PASS          %s'%('YES' if ok else 'NO')); print('--- rsyncbolt output ---'); print(combined.rstrip()); return 0 if ok else 1
def paid_speed(exe,version):
    shutil.rmtree(BASE,ignore_errors=True); os.makedirs(BASE); fake=os.path.join(BASE,'ssh_loopback'); make_fake_ssh(fake); src=os.path.join(BASE,'large.bin'); native=os.path.join(BASE,'native'); bolt=os.path.join(BASE,'bolt'); os.mkdir(native); os.mkdir(bolt)
    n=SIZE_MIB*1024*1024; final_n=n+len(PATCH_BYTES); make_sparse(src,n); make_sparse(os.path.join(native,'large.bin'),n); make_sparse(os.path.join(bolt,'large.bin'),n)
    st=os.stat(src); mt=int(getattr(st,'st_mtime_ns',int(st.st_mtime*1e9))); helper,sibling=helper_for_platform(); write_state(src,bolt+'/',helper,sibling,n,mt)
    with open(src,'ab') as f: f.write(PATCH_BYTES)
    rs=['rsync','-pt','-e',fake,src,HOST+':'+native+'/']; rb=[exe,'-pt','-e',fake,src,HOST+':'+bolt+'/']
    rs_s,_,_=timed(rs,'RSYNC_COMMAND'); rb_s,rb_out,_=timed(rb,'RSYNCBOLT_COMMAND'); speed=rs_s/rb_s if rb_s else 0.0
    ok=exact(src,final_n) and exact(os.path.join(native,'large.bin'),final_n) and exact(os.path.join(bolt,'large.bin'),final_n)
    print('RSYNCBOLT_PUBLIC_LARGE_PAID_SPEED'); print('VERSION    %s'%version); print('SIZE_MIB   %d'%SIZE_MIB); print('PATCH_KIB  %d'%(len(PATCH_BYTES)//1024)); print('RSYNC      %.6f s'%rs_s); print('RSYNCBOLT  %.6f s'%rb_s); print('SPEEDUP    %.2fx'%speed); print('EXACT      %s'%('YES' if ok else 'NO')); print('30X_PLUS   %s'%('YES' if speed>=30.0 else 'NO')); print('PASS       %s'%('YES' if ok and speed>=30.0 else 'NO')); print('--- rsyncbolt stdout ---'); print(rb_out.rstrip()); print('FIXTURE     %s'%BASE); print('REPEAT_CMD  %s'%(' '.join(q(x) for x in rb))); return 0 if ok and speed>=30.0 else 1
def main():
    print('RSYNCBOLT_TEST_BUILD '+BUILD); exe=os.path.abspath('./rsyncbolt')
    if not os.path.isfile(exe) or not os.access(exe,os.X_OK): print('FAIL: expected executable ./rsyncbolt'); return 1
    out,err=run([exe,'--version'],'RSYNCBOLT_COMMAND'); version=(out+err).strip()
    if 'FREE' in version.upper(): return free_gate(exe,version)
    if 'PAID' in version.upper(): return paid_speed(exe,version)
    print('FAIL: unrecognized edition: '+version); return 1
if __name__=='__main__': sys.exit(main())
