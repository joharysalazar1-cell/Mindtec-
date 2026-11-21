import os,subprocess,sys,unittest
from pathlib import Path

@unittest.skipUnless(os.name=='nt','Windows native job isolation')
class Tests(unittest.TestCase):
 def test_normal_exit_keeps_success_code_for_scheduled_stop(self):
  code="from windows_job import protect_current_process;assert protect_current_process()['enabled'];raise SystemExit(0)"
  completed=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parent,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
  self.assertEqual(completed.returncode,0,completed.stderr.decode(errors='replace'))
 def test_abrupt_supervisor_death_terminates_owned_child(self):
  import ctypes as C
  from ctypes import wintypes as W
  k=C.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE;k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.WaitForSingleObject.restype=W.DWORD;k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
  code="from windows_job import protect_current_process;import subprocess,sys,time;assert protect_current_process()['enabled'];c=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);print(c.pid,flush=True);time.sleep(60)"
  parent=subprocess.Popen([sys.executable,'-u','-c',code],cwd=Path(__file__).parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
  handle=None
  try:
   line=parent.stdout.readline();self.assertTrue(line.strip(),parent.stderr.read() if parent.poll() is not None else 'No child reported');pid=int(line)
   handle=k.OpenProcess(0x100000,False,pid);self.assertTrue(handle);self.assertEqual(k.WaitForSingleObject(handle,0),258)
   parent.kill();parent.wait(timeout=10);self.assertEqual(k.WaitForSingleObject(handle,10000),0,'Owned observer survived abrupt supervisor termination')
  finally:
   if parent.poll() is None:parent.kill();parent.wait(timeout=10)
   if handle:k.CloseHandle(handle)
   parent.stdout.close();parent.stderr.close()

if __name__=='__main__':unittest.main()
