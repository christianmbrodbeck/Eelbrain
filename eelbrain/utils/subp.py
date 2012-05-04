'''

for permission errors: try ``os.chmod`` or ``os.chown``


subprocess documentation
------------------------

http://docs.python.org/library/subprocess.html
http://www.doughellmann.com/PyMOTW/subprocess/
http://explanatorygap.net/2010/05/10/python-subprocess-over-shell/
http://codeghar.wordpress.com/2011/12/09/introduction-to-python-subprocess-module/


Created on Mar 4, 2012

@author: christian
'''

import os
import subprocess
import tempfile
import re
import fnmatch

from eelbrain import ui


__all__ = [
#           'forward',
           'kit2fiff', 
           'process_raw', 
           'set_mne_dir',
           'mne_experiment'
           ] 

# keep track of whether the mne dir has been successfully set
_mne_dir = None


def set_mne_dir(mne=None, freesurfer=None):
    """
    Set the directory where mne is installed. E.g. ::
    
        >>> set_mne_dir('~/unix_apps/mne-2.7.3')
    
    """
    if mne:
        mne = os.path.expanduser(mne)
        if os.path.exists(mne):
            os.environ['MNE_ROOT'] = mne
            os.environ['DYLD_LIBRARY_PATH'] = os.path.join(mne, 'lib')
            
            mne_bin = os.path.join(mne, 'bin')
            if 'PATH' in os.environ:
                os.environ['PATH'] += ':%s' % mne_bin
            else:
                os.environ['PATH'] = mne_bin
        else:
            raise IOError("%r does not exist" % mne)
    
    if freesurfer:
        freesurfer = os.path.expanduser(freesurfer)
        if os.path.exists(mne):
            os.environ['FREESURFER_HOME'] = freesurfer
        else:
            raise IOError("%r does not exist" % freesurfer)


    
    global _mne_dir
    _mne_dir = mne
    



class marker_avg_file:
    def __init__(self, path):
        # Parse marker file, based on Tal's pipeline:
        regexp = re.compile(r'Marker \d:   MEG:x= *([\.\-0-9]+), y= *([\.\-0-9]+), z= *([\.\-0-9]+)')
        output_lines = []
        for line in open(path):
            match = regexp.search(line)
            if match:
                output_lines.append('\t'.join(match.groups()))
        txt = '\n'.join(output_lines)
        
        fd, self.path = tempfile.mkstemp(suffix='hpi', text=True)
        f = os.fdopen(fd, 'w')
        f.write(txt)
        f.close()
    
    def __del__(self):
        os.remove(self.path)


class mne_experiment:
    def __init__(self, megdir=None, subject=None, experiment=None):
        """
        directory : str
            the base directory for the experiment
        
        ename : str
            the name of the experiment as it appears in file names
        
        """
        if megdir:
            megdir = os.path.expanduser(megdir)
        else:
            msg = "Please select the meg directory of your experiment"
            megdir = ui.ask_dir("Select Directory", msg, True)
        
        self._megdir = megdir
        self._subject = subject
        self._experiment = experiment
        
        self._subjects = [p for p in os.listdir(megdir) if not p.startswith('.')]
        
        # path elements
        sub = '{subject}'
        exp = '{experiment}'
        rawdir = os.path.join(megdir, sub, 'raw')
        
        # kit2fiff
        self.temp_mrk = os.path.join(rawdir, '_'.join((sub, exp, 'marker.txt')))
        self.temp_elp = os.path.join(rawdir, '*.elp')
        self.temp_hsp = os.path.join(rawdir, '*.hsp')
        self.temp_sns = '~/Documents/Eclipse/Eelbrain Reloaded/aux_files/sns.txt'
        self.temp_rawtxt = os.path.join(rawdir, '_'.join((sub, exp, 'raw.txt')))
        self.temp_rawfif = os.path.join(rawdir, '_'.join((sub, exp, 'raw.fif')))
    
    def __repr__(self):
        args = [('megdir', repr(self._megdir))]
        if self._subject is not None:
            args.append(('subject', repr(self._subject)))
        if self._experiment is not None:
            args.append(('experiment', repr(self._experiment)))
        
        args = ', '.join(['='.join(pair) for pair in args])
        return "mne_experiment(%s)" % args
    
    def get(self, name):
        fmt = dict(subject = self._subject,
                   experiment = self._experiment)
        
        if name == 'mrk':
            path = self.temp_mrk.format(**fmt)
        elif name == 'elp':
            path = self.temp_elp.format(**fmt)
        elif name == 'hsp':
            path = self.temp_hsp.format(**fmt)
        elif name == 'sns':
            path = self.temp_sns.format(**fmt)
        elif name == 'rawtxt':
            path = self.temp_rawtxt.format(**fmt)
        elif name == 'rawfif':
            path = self.temp_rawfif.format(**fmt)
        else:
            raise KeyError("No path for %r" % name)
        
        # assert the presence of the file
        directory, name = os.path.split(path)
        if '*' in name:
            match = [n for n in os.listdir(directory) if fnmatch.fnmatch(n, name)]
            if len(match) == 1:
                path = os.path.join(directory, match[0])
            elif len(match) > 1:
                err = "More than one files match %r: %r" % (path, match)
                raise IOError(err)
            else:
                raise IOError("no file found for %r" % path)
        
        path = os.path.expanduser(path)
        return path
    
    def set(self, subject=None, experiment=None):
        if subject is not None:
            self._subject = subject
        if experiment is not None:
            self._experiment = experiment



def _format_path(path, fmt, is_new=False):
    "helper function to format the path to mne files"
    if not isinstance(path, basestring):
        path = os.path.join(*path)
    
    if fmt:
        path = path.format(**fmt)
    
    # test the path
    path = os.path.expanduser(path)
    if is_new or os.path.exists(path):
        return path
    else:
        raise IOError("%r does not exist" % path)
    


def kit2fiff(paths=dict(mrk = None,
                        elp = None,
                        hsp = None,
                        sns = None,
                        rawtxt = None,
                        rawfif = None),
             sfreq=1000, lowpass=100, highpass=0,
             stim=xrange(168, 160, -1),  stimthresh=1,
             aligntol=25):
    """
    Calls the ``mne_kit2fiff`` binary which reads multiple input files and 
    combines them into a fiff file. Implemented after Gwyneth's Manual; for 
    more information see the mne manual (p. 222). 
    
    All filenames can be specified either as string, or as tuple of strings.
    Tuples are converted to paths with::
    
        >>> os.path.join(*arg).format(**fmt)
    
    where ``fmt`` contains the following entries:
    
    ``meg_sdir``
        input argument
    ``experiment``
        input argument
    ``subject``
        last directory name in ``meg_sdir``
    
    Directories can contain the user home shortcut (``~``). Other Arguments are:
    
    mrk, elp, hsp, raw, out, sns : str or tuple (see above)
        input files
        
    experiment : str
        The experiment name as it appears in file names.
    
    highpass : scalar
        The highpass filter corner frequency (only for file info, does not
        filter the data). 0 Hz for DC recording.
    
    lowpass : scalar
        like highpass
    
    meg_sdir : str or tuple (see above)
        Path to the subjects's meg directory. If ``None``, a file dialog is 
        displayed to ask for the directory.
    
    sfreq : scalar
        samplingrate of the data
    
    stimthresh : scalar
        The threshold value used when synthesizing the digital trigger channel
    
    stim : iterable over ints
        trigger channels that are used to reconstruct the event cue value from 
        the separate trigger channels. The default ``xrange(168, 160, -1)`` 
        reconstructs the values sent through psychtoolbox.
    
    """
    if not _mne_dir:
        raise IOError("mne-dir not set. See mne_link.set_mne_dir.")
    
    # get all the paths
    mrk_path = paths.get('mrk')
    elp_file = paths.get('elp')
    hsp_file = paths.get('hsp')
    sns_file = paths.get('sns')
    raw_file = paths.get('rawtxt')
    out_file = paths.get('rawfif')
    
    # convert the marker file
    mrk_file = marker_avg_file(mrk_path)
    hpi_file = mrk_file.path

    # make sure target path exists
    out_dir = os.path.dirname(out_file)
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
    elif os.path.exists(out_file):
        if not ui.ask("Overwrite?", "Target File Already Exists at: %r. Should "
                      "it be replaced?" % out_file):
            return
        
    cmd = [os.path.join(_mne_dir, 'bin', 'mne_kit2fiff'),
           '--elp', elp_file,
           '--hsp', hsp_file,
           '--sns', sns_file,
           '--hpi', hpi_file,
           '--raw', raw_file,
           '--out', out_file,
           '--stim', ':'.join('%i' % s for s in stim), # '161:162:163:164:165:166:167:168'
           '--sfreq', sfreq,
           '--aligntol', aligntol,
           '--lowpass', lowpass,
           '--highpass', highpass,
           '--stimthresh', stimthresh,
           ]
    
    _run(cmd)



def process_raw(raw, save='{raw}_filt', args=[], **kwargs):
    """
    Calls ``mne_process_raw`` to process raw fiff files. All 
    options can be submitted in ``args`` or as kwargs (for a description of
    the options, see mne manual 2.7.3, ch. 4 / p. 41)
    
    raw : str(path)
        Source file. 
    save : str(path)
        Destination file. ``'{raw}'`` will be replaced with the raw file path
        without the extension.
    args : list of str
        Options that do not require a value (e.g., to specify ``--filteroff``,
        use ``args=['filteroff']``). 
    kwargs : 
        Options that require values.
    
    Example::
    
        >>> process_raw('/some/file_raw.fif', highpass=8, lowpass=12)
    
    """
    raw_name, _ = os.path.splitext(raw)
    if raw_name.endswith('_raw'):
        raw_name = raw_name[:-4]
    
    save = save.format(raw=raw_name)
    
    cmd = [os.path.join(_mne_dir, 'bin', 'mne_process_raw'),
           '--raw', raw,
           '--save', save]
    
    for arg in args:
        cmd.append('--%s' % arg)
    
    for key, value in kwargs.iteritems():
        cmd.append('--%s' % key)
        cmd.append(value)
    
    _run(cmd)



def _run(cmd, v=True):
    """
    cmd: list of strings
        command that is submitted to subprocess.Popen.
    v : bool
        verbose mode
    
    """
    if v:
        print "> COMMAND:"
        for line in cmd:
            print repr(line)
    
    cmd = [str(c) for c in cmd]
    sp = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = sp.communicate()
    
    if v:
        print "\n> OUT:"
        print stdout
        print '\n> ERROR:'
        print stderr



def forward(mri_dir, fif_file, subject, coreg=True):
    """
    . Short instructions 
    below, for more information see section XI of Gwyneth's manual. 
    
    Arguments:
    
    mri_sdir : str(path)
        the subjects's mri dir
    meg : str(path)
        the subject's meg dir
    coreg : bool
        Opens ``mne_analyze`` to setup the meg/mri coregistration (for 
        instructions see below)
    
    Procedure:
    
    #. File > Load Surface: select the subject`s directory and "Inflated"
    #. File > Load digitizer data: select the fiff file
    #. View > Show viewer
       
       a. ``Options``: Switch cortical surface display off, make 
          scalp transparent. ``Done``
       
    #. Adjust > Coordinate Alignment: set LAP, Nasion and RAP. ``Align using 
       fiducials``. 
    
       a. Run ``ICP alignment`` with 20 steps
       b. ``Save MRI set``, ``Save default``
    
    This will create:
     - mri/<subject>/mri/T1-neuromag/sets/COR-<username>-<date created>-<arbitrary number>.
 
    """
    mri_sdir = os.path.join(mri_dir, subject)
    bemdir = os.path.join(mri_sdir, 'bem')
    
    # Gwyneth XXX
    for name in ['inner_skull', 'outer_skull', 'outer_skin']:
        src = os.path.join(bemdir, 'watershed', '%s_%s_surface' % (subject, name))
        dest = os.path.join(bemdir, '%s.surf' % name)
        if os.path.islink(dest):
#            print "replacing symlink: %r" % dest
            os.remove(dest)
        os.symlink(src, dest)
        # can raise an OSError: [Errno 13] Permission denied
    
    os.environ['SUBJECTS_DIR'] = mri_dir
    fif_dir, _ = os.path.split(fif_file)
    if coreg:
        os.chdir(fif_dir)
        p = subprocess.Popen('. $MNE_ROOT/bin/mne_setup_sh; mne_analyze', shell=True)
        print "Waiting for mne_analyze to be closed..."
        p.wait() # causes the shell to be unresponsive until mne_analyze is closed
#    p = subprocess.Popen(['%s/bin/mne_setup' % _mne_dir],
#                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#    p.wait()
#    a, b = p.communicate('mne_analyze')
#    p = subprocess.Popen('mne_analyze')
# Gwyneth's Manual, XII
## SUBJECTS_DIR is MRI directory according to MNE 17
    
    
    cmd = [os.path.join(_mne_dir, 'bin', "mne_setup_forward_model"),
           '--subject', subject,
           '--surf',
           '--ico', 4,
           '--homog']
    
    _run(cmd)
    # -> /Users/christian/Data/eref/mri/R0368/bem/R0368-5120-bem-sol.fif
    
    
    cmd = [os.path.join(_mne_dir, 'bin', "mne_do_forward_solution"),
           '--subject', subject,
           '--src', os.path.join(bemdir, '%s-ico-4-src.fif' % subject),
           '--bem', os.path.join(bemdir, '%s-5120-bem-sol.fif' % subject), 
           '--meas', fif_file,
            ##'<subj>/<experiment_folder>/RawGrandAve.fif',
           '--megonly']
    
    _run(cmd)
    # -> /Users/christian/Data/eref/meg/R0368/myfif/R0368_eref3_raw-R0368-ico-4-src-fwd.fif...done
#    fwd_file ='-fwd' 
#    cov_file = ''
#    
#    cmd = [os.path.join(_mne_dir, 'bin', "mne_do_inverse_operator"),
#           '--fwd', fwd_file, 
#           '--meg', 
#           '--depth', 
#           '--megreg', '0.1',
#           '--senscov', cov_file]
    # -> (creates RawGrandAve-7-fwd-inv.fif). 



def noise_covariance():
    """
    
    """
    pass
    # mne.cov.compute_covariance iterates over an Epoch file
    



