#!/usr/bin/env python
#
# Name: Repair Cycorder .mov Script
# Author: Donald Kjer <xylor77@yahoo.com>
#
# ==============================================================
# IF YOU FIND THIS SCRIPT USEFUL, FEEL FREE TO BUY ME SOME BEER!
# Donation link ($5 recommended): https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=xylor77%40yahoo%2ecom&lc=US&item_name=Repair%20Cycorder%20%2emov%20Script&item_number=RCM1&currency_code=USD&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHosted
# 
# ==============================================================
# 
# See the 'COPYING.txt' file for full GPL licensing information.  
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from struct import unpack, pack
import sys, os, math, getopt

VERSION=1.0
MJPG_MARKER = '\xff\xd8\xff\xe1\x00\x2a\x00\x00\x00\x00mjpg'
CHUNK_SIZE=1024*1024

def read_mdat(f, o, max_read, offset, verbose):
    chunk = ""
    video_samples = 0
    audio_samples = 0
    audio_chunks = 0

    video_data = []
    audio_data = []
    sync_data = []
    video_samples_since_sync = 0
    audio_samples_since_sync = 0
    sync_carryover = 0
    sync_duration_total = 0
    read_if_exhausted = True

    while True:
        # Read more if we are low on data.
        if read_if_exhausted and len(chunk) < (CHUNK_SIZE / 2):
            bytes_to_read = CHUNK_SIZE
            # Limit how much to we read from our source; we don't want to run past the mdat section.
            if max_read is not None:
                if bytes_to_read > max_read:
                    bytes_to_read = max_read
                    # We have hit the end the mdat section.  Don't read anymore.
                    read_if_exhausted = False
                max_read -= bytes_to_read
            new_chunk = f.read(bytes_to_read)
            if len(new_chunk) < CHUNK_SIZE:
                # We have read to the end of the file.  Don't read anymore.
                read_if_exhausted = False
            o.write(new_chunk)
            chunk = chunk + new_chunk

        # Look for an 'mjpg' marker.  Don't include the last 4 bytes,
        # to ensure we include the 'size' field in the data we search.
        marker_pos = chunk[:-4].find(MJPG_MARKER)

        # If we didn't find one, get out.
        if 0 != marker_pos:
            # Did we reach the end of the file?
            if -1 == marker_pos:
                # Assume the rest of the file is audio.
                chunk_audio_samples = (len(chunk) / 2)
                # Don't bother if we only read 1 byte, for some reason.
                if 0 == chunk_audio_samples:
                    break
            else:
                chunk_audio_samples = (marker_pos / 2)
            audio_samples += chunk_audio_samples
            time_delta = int(float(chunk_audio_samples) / 44100 * 10000)
            audio_chunks += 1
            if verbose:
                print "A%d: %d, %f, %d, %d, %d" % (audio_chunks, time_delta, float(audio_samples) / 44100, chunk_audio_samples, audio_samples, offset)
            sys.stdout.write(".")
            sys.stdout.flush()
            audio_data.append( (audio_samples, offset) )
            audio_samples_since_sync += chunk_audio_samples
            offset += marker_pos

        # Flush sync data
        if 0 != marker_pos and video_samples_since_sync > 1:
            # Calculate the average duration of each video frame, based on how much audio sample data we have.
            audio_time_since_sync = float(audio_samples_since_sync) / 44100 * 10000 + sync_carryover
            frame_duration = int(audio_time_since_sync / float(video_samples_since_sync))

            # Keep the carryover for future sync calculations.
            sync_duration = frame_duration * video_samples_since_sync
            sync_duration_total += sync_duration
            sync_carryover = audio_time_since_sync - float(sync_duration)
            sync_data.append( (video_samples_since_sync, frame_duration) )
            if verbose:
                print "S%d: %d, %d, %f, %d, %f, %d" % (audio_chunks, video_samples_since_sync, audio_samples_since_sync, audio_time_since_sync, frame_duration, sync_carryover, sync_duration_total)
            video_samples_since_sync = 0
            audio_samples_since_sync = 0

        if -1 == marker_pos:
            #*TODO: Handle reading more from the file?
            if verbose:
                print "EOF"
            print 
            break

        # We found a video sample.
        video_samples += 1
        # Strip off the marker.
        chunk = chunk[marker_pos + len(MJPG_MARKER):]
        # Extract the size field.
        size = unpack('>L', chunk[:4])[0]
        chunk = chunk[4:]
        if verbose:
            print "V%d: %d, %d" % (video_samples, size, offset)
        video_data.append( (size, offset) )
        video_samples_since_sync += 1
        offset += size
        # Reduce the size left for this sample by the amount we have aready read.
        size -= (len(MJPG_MARKER) + 4)
        # Skip past the contents of this sample.
        if len(chunk) < size:
            # The rest of the chunk is just part of the sample.  Discard it.
            size -= len(chunk)
            # We need to read another chunk.
            if read_if_exhausted:
                bytes_to_read = CHUNK_SIZE
                # Limit how much to we read from our source; we don't want to run past the mdat section.
                if max_read is not None:
                    if bytes_to_read > max_read:
                        bytes_to_read = max_read
                        # We have hit the end the mdat section.  Don't read anymore.
                        read_if_exhausted = False
                    max_read -= bytes_to_read
                chunk = f.read(bytes_to_read)

                if len(chunk) < CHUNK_SIZE:
                    # We have read to the end of the file.  Don't read anymore.
                    read_if_exhausted = False
                o.write(chunk)

        # *TODO: Handle samples larger than 1 MB?
        # Remove the sample portion from this chunk.
        chunk = chunk[size:]

    # Rebalance sync_data:
    if len(sync_data) > 1:
        rebalanced = False
        if len(sync_data) > 2:
            # Set the last sync to the average of all but the first and last sync set.
            total_samples = 0
            total_duration = 0
            for (samples, duration) in sync_data[1:-1]:
                total_samples += samples
                total_duration += duration * samples
            average = 0
            if total_samples > 0:
                average = total_duration / total_samples
            
            # Extract the current first/last sync set totals.
            (first_sample, first_duration) = sync_data[0]
            (last_sample, last_duration) = sync_data[-1]
            total_samples = first_sample + last_sample
            total_duration = (first_duration * first_sample) + (last_duration * last_sample)

            # Determine if we have enough duration to set the last sync to the average duration.
            if total_duration > (last_sample * average) and first_sample > 0:
                # Yes, set the last sync to the average value, and use the rest of the duration for the first sync.
                sync_data[-1] = (last_sample, average)
                total_duration -= (last_sample * average)
                sync_data[0] = (first_sample, total_duration / first_sample)
        if not rebalanced:
            # Try to just average out the first and last sync sets.
            (first_sample, first_duration) = sync_data[0]
            (last_sample, last_duration) = sync_data[-1]
            total_samples = first_sample + last_sample
            total_duration = (first_duration * first_sample) + (last_duration * last_sample)
            average = total_duration / total_samples
            sync_data[0] = (first_sample, average)
            sync_data[1] = (last_sample, average)

    return (video_data, audio_data, sync_data)

def construct_moov(moov, video_data, audio_data, sync_data):
    # Read in the 'moov' template file.
    moov_file = open('moov_template', 'rb')
    template = moov_file.read()
    moov_file.close()

    # Construct a samples to chunks table for audio information.
    stsc = []

    prev_samples = 0
    prev_sample_total = 0
    chunk_num = 1

    for (sample_total, offset) in audio_data:
        samples = sample_total - prev_sample_total

        if samples != prev_samples:
            stsc.append( (chunk_num, samples) )

        prev_samples = samples
        prev_sample_total = sample_total
        chunk_num += 1

    # Calculate duration/count fields.
    total_audio_samples = audio_data[-1][0]
    total_duration = int(math.ceil(float(total_audio_samples) / 44100 * 1000))
    print "mvhd.duration = %d" % total_duration
    template = template[:0x20] + pack('>L', total_duration) + template[0x24:]
    video_duration = int(math.ceil(float(total_audio_samples) / 44100 * 10000))

    print "trak(video).tkhd.duration = %d" % total_duration
    template = template[:0x98] + pack('>L', total_duration) + template[0x9c:]
    print "trak(video).mdia.mdhd.duration = %d" % video_duration
    template = template[:0xf8] + pack('>L', video_duration) + template[0xfc:]

    # Calculate the size of our replacement sections.
    #### VIDEO
    stsd_size = 0x66
    stts_size = 16 + len(sync_data) * 8
    stsc_size = 0x1c
    stsz_size = 20 + len(video_data) * 4
    stco_size = 16 + len(video_data) * 4

    # Replace the 'stbl' size
    stbl_size = 8 + stsd_size + stts_size + stsc_size + stsz_size + stco_size
    template = template[:0x199] + pack('>L', stbl_size) + template[0x19d:]

    vmhd_size = 0x14
    hdlr_size = 0x2c
    dinf_size = 0x24

    # Replace the 'minf' size
    minf_size = 8 + vmhd_size + hdlr_size + dinf_size + stbl_size
    template = template[:0x12d] + pack('>L', minf_size) + template[0x131:]

    mdhd_size = 0x20
    hdlr_size = 0x2d

    # Replace the 'mdia' size
    mdia_size = 8 + mdhd_size + hdlr_size + minf_size
    template = template[:0xd8] + pack('>L', mdia_size) + template[0xdc:]

    tkhd_size = 0x5c

    # Replace the video 'trak' size
    vtrak_size = 8 + tkhd_size + mdia_size
    template = template[:0x74] + pack('>L', vtrak_size) + template[0x78:]


    ### AUDIO
    astsd_size = 0x34
    astts_size = 0x18
    astsc_size = 16 + len(stsc) * 12 
    astsz_size = 0x14
    astco_size = 16 + len(audio_data) * 4
    astbl_size = 8 + astsd_size + astts_size + astsc_size + astsz_size + astco_size
    template = template[:0x171b8] + pack('>L', astbl_size) + template[0x171bc:]

    asmhd_size = 0x10
    ahdlr_size = 0x2c
    adinf_size = 0x24
    aminf_size = 8 + asmhd_size + ahdlr_size + adinf_size + astbl_size
    template = template[:0x17150] + pack('>L', aminf_size) + template[0x17154:]

    amdhd_size = 0x20
    ahdlr_size = 0x2d
    amdia_size = 8 + amdhd_size + ahdlr_size + aminf_size
    template = template[:0x170fb] + pack('>L', amdia_size) + template[0x170ff:]

    atkhd_size = 0x5c
    atrak_size = 8 + atkhd_size + amdia_size
    template = template[:0x17097] + pack('>L', atrak_size) + template[0x1709b:]

    mvhd_size = 0x6c
    moov_size = 8 + mvhd_size + vtrak_size + atrak_size
    template = pack('>L', moov_size) + template[0x4:]

    # Write out the 'moov' template into a new 'moov' file, up to the video stts section.
    moov.write(template[:0x207])

    print "trak(video).mdia.minf.stbl.stts.numEntries = %d" % len(sync_data)
    moov.write(pack('>L', stts_size))
    moov.write('stts')
    moov.write(pack('>LL', 0, len(sync_data)))

    if verbose:
        print "entry\tsampCnt\tsampDur"
    entry = 1
    for (count, duration) in sync_data:
        if verbose:
            print "%d\t%d\t%d" % (entry, count, duration)
        moov.write(pack('>LL', count, duration))
        entry += 1

    # Copy the template's 'stsc' section.
    moov.write(template[0x7fe7:0x8003])

    # Calculate the size of our stsz replacement section.
    print "trak(video).mdia.minf.stbl.stsz.numEntries = %d" % len(video_data)
    moov.write(pack('>L', stsz_size))
    moov.write('stsz')
    moov.write(pack('>LLL', 0, 0, len(video_data)))

    entry = 1
    if verbose:
        print "1\t",
    for (size, offset) in video_data:
        if verbose:
            print "%d\t" % size,
            if entry % 7 == 0:
                print
                print "%d\t" % (entry + 1),
        moov.write(pack('>L', size))
        entry += 1
    if verbose:
        print


    print "trak(video).mdia.minf.stbl.stco.numEntries = %d" % len(video_data)
    moov.write(pack('>L', stco_size))
    moov.write('stco')
    moov.write(pack('>LL', 0, len(video_data)))

    entry = 1
    if verbose:
        print "1\t",
    for (size, offset) in video_data:
        if verbose:
            print "%d\t" % size,
            if entry % 7 == 0:
                print
                print "%d\t" % (entry + 1),
        moov.write(pack('>L', offset))
        entry += 1
    if verbose:
        print

    # Generate audio sample tables.
    print "trak(audio).tkhd.duration = %d" % total_duration
    template = template[:0x170bb] + pack('>L', total_duration) + template[0x170bf:]
    print "trak(audio).mdia.mdhd.duration = %d" % total_audio_samples
    template = template[:0x1711b] + pack('>L', total_audio_samples) + template[0x1711f:]
    print "trak(audio).mdia.minf.stbl.stts.numEntries = 1"
    if verbose:
        print "entry\tsampCnt\tsampDur"
        print "1\t%d\t1" % total_audio_samples

    # Copy the template up to the audio 'stts' section.
    moov.write(template[0x17097:0x17204])
    moov.write(pack('>LL', total_audio_samples, 1))

    print "trak(audio).mdia.minf.stbl.stsc.numEntries = %d" % len(stsc)
    moov.write(pack('>L', astsc_size))
    moov.write('stsc')
    moov.write(pack('>LL', 0, len(stsc)))

    if verbose:
        print "entry\t1st Chunk\tsamp/chunk\tdesc ID"
    entry = 1

    for (chunk_num, samples) in stsc:
        if verbose:
            print "%d\t%d\t%d\t%d" % (entry, chunk_num, samples, 1)
        entry += 1
        moov.write(pack('>LLL', chunk_num, samples, 1))

    # Generate an 'stsz' section.
    print "trak(audio).mdia.minf.stbl.stsz.numEntries = %d" % total_audio_samples
    moov.write(pack('>L', 0x14))
    moov.write('stsz')
    moov.write(pack('>LLL', 0, 2, total_audio_samples))

    print "trak(audio).mdia.minf.stbl.stco.numEntries = %d" % len(audio_data)
    moov.write(pack('>L', astco_size))
    moov.write('stco')
    moov.write(pack('>LL', 0, len(audio_data)))

    entry = 1
    if verbose:
        print "1\t",
    for (sample_total, offset) in audio_data:
        if verbose:
            print "%d\t" % offset,
            if entry % 6 == 0:
                print
                print "%d\t" % (entry + 1),
        entry += 1
        moov.write(pack('>L', offset))
    if verbose:
        print

def repair_qt(input_filename, output_filename, verbose):
    f = open(input_filename, 'rb')
    o = open(output_filename, 'wb')
    offset = 0
    wide_offset = None
    while True:
        atom_hdr = f.read(8)
        o.write(atom_hdr)
        read_bytes = 8
        if "" == atom_hdr:
            break
        size = unpack('>L', atom_hdr[:4])[0]
        type = atom_hdr[4:]
        # Check for extended size
        if 1 == size:
            extended = f.read(8)
            o.write(extended)
            read_bytes += 8
            if "" == extended:
                break
            size = unpack('>Q', extended)[0]
        offset += read_bytes

        print "Type: '%s', size: %d" % (type, size)

        if "wide" == type:
            wide_offset = offset - read_bytes
        elif "mdat" == type:
            max_read = None
            if size != 0:
                max_read = size
            print "Attempting to reconstruct sample tables."
            (video_data, audio_data, sync_data) = read_mdat(f, o, max_read, offset, verbose)
            mdat_size = o.tell() - offset + 8
            print "Reconstructing 'moov' atom."
            construct_moov(o, video_data, audio_data, sync_data)
            # Update mdat size
            print "New mdat size: %d" % mdat_size
            # If this is larger than 32 bits, then we need to consume the 'wide' portion to make this an extended size.
            if mdat_size > 0xFFFFFFFF:
                # In order for this to work, we need to have a 'wide' atom just before this one (or already have an extended size)
                if read_bytes != 16 and wide_offset != offset - 16:
                    # We can't write this size out...
                    print "Could not find a properly positioned 'wide' atom to write extended size to."
                    break
                if read_bytes != 16:
                    print "Replacing 'wide' atom with extended 'mdat' size."
                # Increase the mdat size by the extended header size.
                mdat_size += 8
                o.seek(wide_offset)
                # A size of 1 has a special meaning: extended size
                o.write(pack('>L', 1))
                # Rewrite the atom type to be earlier in the file.
                o.write(type)
                # Now we have enough room to write a 64-bit size:
                o.write(pack('>Q', mdat_size))
            else:
                o.seek(offset - 8)
                o.write(pack('>L', mdat_size))
            break
        elif size < read_bytes:
            print "Invalid atom size."
            break
        else:
            # Copy size - 8 bytes.
            bytes_to_copy = size - 8
            offset += bytes_to_copy
            while bytes_to_copy >= CHUNK_SIZE:
                chunk = f.read(CHUNK_SIZE)
                o.write(chunk)
                bytes_to_copy -= CHUNK_SIZE
            if bytes_to_copy > 0:
                chunk = f.read(bytes_to_copy)
                o.write(chunk)
            #f.seek(size - 8, os.SEEK_CUR)
    o.close()
    f.close()

def usage():
    print """Usage: %s [OPTIONS] [INPUT_MOV] [OUTPUT_MOV]
Repair a Cycorder video specified by INPUT_MOV.  Repaired video will be written to OUTPUT_MOV.
    
OPTIONS:
    -v, --verbose   print verbose information
    -o, --overwrite overwrite OUTPUT_MOV file if it already exists
    -h, --help      display this help and exit
    --version       output version information and exit
    """ % sys.argv[0]

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hvo", ["help", "verbose", "overwrite", "version"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    verbose = False
    overwrite = False
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-v", "--verbose"):
            verbose = True
        elif opt in ("-o", "--overwrite"):
            overwrite = True
        elif opt == "--version":
            print "%s version %1.1f" % (sys.argv[0], VERSION)
            sys.exit()

    try:
        input_filename = args[0]
        output_filename = args[1]
    except IndexError:
        usage()
        sys.exit(2)

    # Check for file existance. 
    if not os.path.exists(input_filename):
        print "Could not file input file '%s':" % input_filename
        sys.exit(1)
    if os.path.exists(output_filename):
        if not overwrite:
            print "Output file '%s' already exists.  Please rerun with '-o' to overwrite."  % output_filename
            sys.exit(1)
        # If we are allowing overwrite, make sure this is a file.
        if not os.path.isfile(output_filename):
            print "Cannot overwrite Output file '%s'." % output_filename
            sys.exit(1)

    repair_qt(input_filename, output_filename, verbose)

