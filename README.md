repair_cycorder_mov
===================

Python script to repair interrupted Cycorder videos.

This script is used to reconstruct missing a 'moov' atom by reconstructing sample table information needed to repair an incomplete Cycorder .mov file.

Example use:
./repair_cycorder_mov.py my_broken.mov repaired.mov

==============================================================
IF YOU FIND THIS SCRIPT USEFUL, FEEL FREE TO BUY ME SOME BEER!

Donation link ($5 recommended): https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=xylor77%40yahoo%2ecom&lc=US&item_name=Repair%20Cycorder%20%2emov%20Script&item_number=RCM1&currency_code=USD&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHosted

==============================================================

See the 'COPYING.txt' file for GPL licensing information.

After spending some time poring over a hex editor, Dumpster (QuickTime Tools) and the QuickTime File Format (Qtff pdf - .Pdf & Word Free Ebooks Download).  As NFL_Demon and jumpfroggy found at http://modmyi.com/forums/windows-specific-modding-discussion/587461-editing-mov-files-corrupt-cycorder-videos-3.html, since Cycorder didn't finalize the .mov we are left with both a missing 'moov' atom, and an 'mdat' atom with a size of 0. However, simply appending a 'moov' atom from a healthy Cycorder .mov and updating the mdat size is not sufficient to fix a corrupt file. While that may allow the file to be loaded in a QuickTime player, the resulting video would have sample video/audio tables pointing at essentially random locations within the file. You would probably see a black video with crackling noises and snippets of sound.

The following areas of the 'moov' atom need to be reconstructed in order to have the file play correctly:

* mvhd.duration
* (video) trak.tkhd.duration
* (video) trak.mdia.mdhd.duration
* (video) trak.mdia.minf.stbl.stts
** This stts section basically syncs video/audio sample timing. The entire table needs to be rebuilt. Since we do not have the exact timing information for each video frame (presumably this was in Cycorder memory?) we can guess at the timing for each frame based on the rate of audio samples coming in. This produces reasonable results.
* (video) trak.mdia.minf.stbl.stsz
** This stsz section is the table of video sample sizes. This can be reconstructed by scanning the 'mdat' atom for mjpg signatures.
* (video) trak.mdia.minf.stbl.stco
** This stco section is the table of video sample offsets within the .mov file. Again, this can be reconstructed by scanning the 'mdat' atom.
* (audio) trak.tkhd.duration
* (audio) trak.mdia.mdhd.duration
* (audio) trak.mdia.minf.stbl.stts.sampCnt
* (audio) trak.mdia.minf.stbl.stsc
** This stsc section is the samples to chunks table. This can be reconstructed by analyzing the audio information in the 'mdat' atom.
* (audio) trak.mdia.minf.stbl.stsz.numEntries
* (audio) trak.mdia.minf.stbl.stco
** This stco section is the table of audio sample offsets within the .mov file. This can also be reconstructed by scanning the 'mdat' atom.
* Various container sizes also need to be recalculated to account for the replacement table sizes.



