#!/usr/bin/env python3

"""
Loops over events in a data file and displays them, with optional image
cleaning and hillas parameter overlays.

Only events that contain the specified telescope are read and
displayed. Other telescopes and events are skipped over (EventIO data
files have no index table in them, so the events must be read in
sequence to find ones with the appropriate telescope, therefore this
is not a fast operation)
"""

from matplotlib import pyplot as plt
from matplotlib.patches import Ellipse
from tqdm import tqdm

from ctapipe.calib import CameraCalibrator
from ctapipe.core import Tool
from ctapipe.core.traits import *
from ctapipe.image import (tailcuts_clean, hillas_parameters,
                           HillasParameterizationError)
from ctapipe.instrument import CameraGeometry
from ctapipe.io import EventSourceFactory
from ctapipe.visualization import CameraDisplay


class SingleTelEventDisplay(Tool):
    name = "ctapipe-display-single-tel"
    description = Unicode(__doc__)

    infile = Unicode(help="input file to read", default='').tag(config=True)
    tel = Int(help='Telescope ID to display', default=0).tag(config=True)
    channel = Integer(help="channel number to display", min=0, max=1).tag(
        config=True)
    write = Bool(help="Write out images to PNG files", default=False).tag(
        config=True)
    clean = Bool(help="Apply image cleaning", default=False).tag(config=True)
    hillas = Bool(help="Apply and display Hillas parametrization",
                  default=False).tag(config=True)
    samples = Bool(help="Show each sample", default=False).tag(config=True)
    display = Bool(help="Display results in interactive window",
                   default_value=True).tag(config=True)
    delay = Float(help='delay between events in s', default_value=0.01,
                  min=0.001).tag(config=True)
    progress = Bool(help='display progress bar', default_value=True).tag(
        config=True)

    aliases = Dict({'infile': 'EventSourceFactory.input_url',
                    'tel': 'SingleTelEventDisplay.tel',
                    'max-events': 'EventSourceFactory.max_events',
                    'channel': 'SingleTelEventDisplay.channel',
                    'write': 'SingleTelEventDisplay.write',
                    'clean': 'SingleTelEventDisplay.clean',
                    'hillas': 'SingleTelEventDisplay.hillas',
                    'samples': 'SingleTelEventDisplay.samples',
                    'display': 'SingleTelEventDisplay.display',
                    'delay': 'SingleTelEventDisplay.delay',
                    'progress': 'SingleTelEventDisplay.progress'
                    })

    classes = List([EventSourceFactory, CameraCalibrator])

    def setup(self):

        self.event_source = EventSourceFactory.produce(
            config=self.config,
            tool=self
        )
        self.event_source.allowed_tels = [self.tel, ]

        self.calibrator = CameraCalibrator(
            config=self.config,
            tool=self,
            eventsource=self.event_source
        )

        self.log.info('SELECTING EVENTS FROM TELESCOPE {}'.format(self.tel))

    def start(self):

        disp = None

        for event in tqdm(self.event_source,
                          desc='Tel{}'.format(self.tel),
                          total=self.event_source.max_events,
                          disable=~self.progress):

            self.log.debug(event.trig)
            self.log.debug("Energy: {}".format(event.mc.energy))

            self.calibrator.calibrate(event)

            if disp is None:
                geom = event.inst.subarray.tel[self.tel].camera
                self.log.info(geom)
                disp = CameraDisplay(geom)
                # disp.enable_pixel_picker()
                disp.add_colorbar()
                if self.display:
                    plt.show(block=False)

            # display the event
            disp.axes.set_title('CT{:03d} ({}), event {:06d}'.format(
                self.tel, geom.cam_id, event.r0.event_id)
            )

            if self.samples:
                # display time-varying event
                data = event.dl0.tel[self.tel].waveform[self.channel]
                for ii in range(data.shape[1]):
                    disp.image = data[:, ii]
                    disp.set_limits_percent(70)
                    plt.suptitle("Sample {:03d}".format(ii))
                    if self.display:
                        plt.pause(self.delay)
                    if self.write:
                        plt.savefig('CT{:03d}_EV{:10d}_S{:02d}.png'
                                    .format(self.tel, event.r0.event_id, ii))
            else:
                # display integrated event:
                im = event.dl1.tel[self.tel].image[self.channel]

                if self.clean:
                    mask = tailcuts_clean(geom, im, picture_thresh=10,
                                          boundary_thresh=7)
                    im[~mask] = 0.0

                disp.image = im

                if self.hillas:
                    try:
                        ellipses = disp.axes.findobj(Ellipse)
                        if len(ellipses) > 0:
                            ellipses[0].remove()

                        params = hillas_parameters(geom,  image=im)
                        disp.overlay_moments(params, color='pink', lw=3,
                                             with_label=False)
                    except HillasParameterizationError:
                        pass

                if self.display:
                    plt.pause(self.delay)
                if self.write:
                    plt.savefig('CT{:03d}_EV{:010d}.png'
                                .format(self.tel, event.r0.event_id))

        self.log.info("FINISHED READING DATA FILE")

        if disp is None:
            self.log.warning('No events for tel {} were found in {}. Try a '
                             'different EventIO file or another telescope'
                             .format(self.tel, self.infile),
                             )

        pass


if __name__ == '__main__':
    tool = SingleTelEventDisplay()
    tool.run()
