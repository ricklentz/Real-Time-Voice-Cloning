from data_objects.speaker_verification_dataset import SpeakerVerificationDataset
# from ui.speaker_matrix_ui import SpeakerMatrixUI
from datetime import datetime
from time import perf_counter as clock
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
import subprocess
import webbrowser
import visdom
import umap
import sys


class Visualizations:
    def __init__(self, env_name=None):
        if env_name is None:
            env_name = str(datetime.now().strftime("%d-%m %Hh%M"))
        self.env_name = env_name
        
        try:
            self.vis = visdom.Visdom(env=self.env_name, raise_exceptions=True)
        except ConnectionError as e:
            print('No visdom server detected, running a temporary instance...\nRun the command '
                  '\'visdom\' in your CLI to start an external server.', file=sys.stderr)
            subprocess.Popen('visdom')
            self.vis = visdom.Visdom(env=self.env_name)
        webbrowser.open("http://localhost:8097/env/" + self.env_name)
        
        self.loss_win = None
        self.eer_win = None
        self.lr_win = None
        self.implementation_win = None
        self.projection_win = None
        self.implementation_string = ""
        self.last_step = -1
        self.last_update_timestamp = -1
        self.mean_time_per_step = -1
        self.log_params()
        
    def log_params(self):
        import params_data, params_model
        param_string = "<b>Model parameters</b>:<br>"
        for param_name in (p for p in dir(params_model) if not p.startswith('__')):
            value = getattr(params_model, param_name)
            param_string += "\t%s: %s<br>" % (param_name, value)
        param_string += "<b>Data parameters</b>:<br>"
        for param_name in (p for p in dir(params_data) if not p.startswith('__')):
            value = getattr(params_data, param_name)
            param_string += "\t%s: %s<br>" % (param_name, value)
        self.vis.text(param_string, opts={'title': 'Parameters'})
        
    def log_dataset(self, dataset: SpeakerVerificationDataset):
        dataset_string = ""
        for param, value in dataset.get_params().items():
            dataset_string += "<b>%s</b>: %s\n" % (param, value)
        dataset_string += "\n" + dataset.get_logs()
        dataset_string = dataset_string.replace("\n", "<br>")
        self.vis.text(dataset_string, opts={'title': 'Dataset'})
        
    def log_implementation(self, params):
        implementation_string = ""
        for param, value in params.items():
            implementation_string += "<b>%s</b>: %s\n" % (param, value)
            implementation_string = implementation_string.replace("\n", "<br>")
        self.implementation_string = implementation_string
        self.implementation_win = self.vis.text(
            implementation_string, 
            opts={'title': 'Training implementation'}
        )

    def update(self, loss, eer, lr, step):
        self.loss_win = self.vis.line(
            [loss],
            [step],
            win=self.loss_win,
            update='append' if self.loss_win else None,
            opts=dict(
                xlabel='Step',
                ylabel='Loss',
                title='Loss (mean per 10 steps)',
            )
        )
        self.eer_win = self.vis.line(
            [eer],
            [step],
            win=self.eer_win,
            update='append' if self.eer_win else None,
            opts=dict(
                xlabel='Step',
                ylabel='EER',
                title='Equal error rate (mean per 10 steps)'
            )
        )
        self.lr_win = self.vis.line(
            [lr],
            [step],
            win=self.lr_win,
            update='append' if self.lr_win else None,
            opts=dict(
                xlabel='Step',
                ylabel='Learning rate',
                # ytype='log',
                title='Learning rate'
            )
        )
        
        now = clock()
        if self.last_step != -1 and self.implementation_win is not None:
            time_per_step = (now - self.last_update_timestamp) / (step - self.last_step)
            if self.mean_time_per_step == -1:
                self.mean_time_per_step = time_per_step
            else:
                self.mean_time_per_step = self.mean_time_per_step * 0.9 + time_per_step * 0.1
            time_string = "<b>Mean time per step</b>: %dms" % int(1000 * self.mean_time_per_step)
            time_string += "<br><b>Last step time</b>: %dms" % int(1000 * time_per_step)
            self.vis.text(
                self.implementation_string + time_string, 
                win=self.implementation_win,
                opts={'title': 'Training implementation'},
            )
        self.last_step = step
        self.last_update_timestamp = now
        
    def draw_projections(self, embeds, utterances_per_speaker, step):
        n_speakers = len(embeds) // utterances_per_speaker
        ground_truth = np.repeat(np.arange(n_speakers), utterances_per_speaker)
        color_map = cm.hsv(np.linspace(0, 1, n_speakers + 1))
        colors = [color_map[i] for i in ground_truth]
        
        reducer = umap.UMAP()
        projected = reducer.fit_transform(embeds)
        plt.scatter(projected[:, 0], projected[:, 1], c=colors)
        plt.gca().set_aspect('equal', 'datalim')
        plt.title('UMAP projection (step %d)' % step)
        self.projection_win = self.vis.matplot(plt, win=self.projection_win)
        plt.clf()
        
    def draw_speaker_matrix(self, speaker_batch):
        pass