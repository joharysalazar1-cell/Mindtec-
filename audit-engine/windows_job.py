"""Contain this Windows supervisor and future children in a kill-on-close job.

The unnamed, non-inheritable job handle belongs to this process only. Windows
closes it on process termination, including abrupt termination. No foreign PID
is read from a status file or added to the job.
"""
import os

_JOB_HANDLE=None

def protect_current_process():
 global _JOB_HANDLE
 if os.name!='nt':return {'enabled':False,'reason':'Windows job protection is unavailable on this OS'}
 if _JOB_HANDLE is not None:return {'enabled':True,'mode':'kill_on_supervisor_exit'}
 import ctypes as C
 from ctypes import wintypes as W
 class Basic(C.Structure):
  _fields_=[('PerProcessUserTimeLimit',C.c_int64),('PerJobUserTimeLimit',C.c_int64),('LimitFlags',W.DWORD),('MinimumWorkingSetSize',C.c_size_t),('MaximumWorkingSetSize',C.c_size_t),('ActiveProcessLimit',W.DWORD),('Affinity',C.c_size_t),('PriorityClass',W.DWORD),('SchedulingClass',W.DWORD)]
 class IO(C.Structure):
  _fields_=[(name,C.c_uint64) for name in ['ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount']]
 class Extended(C.Structure):
  _fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',C.c_size_t),('JobMemoryLimit',C.c_size_t),('PeakProcessMemoryUsed',C.c_size_t),('PeakJobMemoryUsed',C.c_size_t)]
 k=C.WinDLL('kernel32',use_last_error=True)
 k.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR];k.CreateJobObjectW.restype=W.HANDLE
 k.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD];k.SetInformationJobObject.restype=W.BOOL
 k.SetHandleInformation.argtypes=[W.HANDLE,W.DWORD,W.DWORD];k.SetHandleInformation.restype=W.BOOL
 k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];k.AssignProcessToJobObject.restype=W.BOOL
 k.GetCurrentProcess.argtypes=[];k.GetCurrentProcess.restype=W.HANDLE
 k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
 handle=k.CreateJobObjectW(None,None)
 if not handle:raise C.WinError(C.get_last_error())
 try:
  info=Extended();info.BasicLimitInformation.LimitFlags=0x2000 # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
  if not k.SetInformationJobObject(handle,9,C.byref(info),C.sizeof(info)):raise C.WinError(C.get_last_error())
  if not k.SetHandleInformation(handle,1,0):raise C.WinError(C.get_last_error())
  if not k.AssignProcessToJobObject(handle,k.GetCurrentProcess()):raise C.WinError(C.get_last_error())
 except BaseException:k.CloseHandle(handle);raise
 # Never close explicitly while this process is alive. No handle inheritance,
 # finalizer or destructor can extend its life into the observer processes.
 _JOB_HANDLE=handle
 return {'enabled':True,'mode':'kill_on_supervisor_exit'}
