from __future__ import division

no_clocks = ['hdg', 'spd', 'hnc', 'hnc_tss1', 'hdg_tss1']
known_position_messages = ['gps', 'gps_sea']
known_heading_messages = ['hdg', 'sea', 'pmv', 'adu', 'hnc',
                            'hnc_tss1', 'hdg_tss1']

from pycurrents.data.nmea.asc2bin import field_dict1 as field_dict

adcp_log_fields = ['u_dday', 'offset', 'nbytes', 'ens_num', 'inst_dday']


# generic gga:
i_u_dday = field_dict['gps'].index('u_dday')
i_dday = field_dict['gps'].index('dday')
i_lon = field_dict['gps'].index('lon')
i_lat = field_dict['gps'].index('lat')
i_quality = field_dict['gps'].index('quality')
i_hdop = field_dict['gps'].index('hdop')
# Additional for seapath, merged from psxn20 message
iS_horiz_qual = field_dict['gps_sea'].index('horiz_qual')



def good_gps(G, max_q = 3):
    if G[i_quality] > 0 and G[i_quality] <= max_q:
        if G[i_hdop] < 7:
            return True
    return False

def good_gps_sea(G):
    if good_gps(G, 5) and G[iS_horiz_qual] <= 1:
        return True
    return False

def txy_interp(t, Gs):
    G0, G1 = Gs
    dtfrac = (t - G0[0]) / (G1[0] - G0[0])
    t = G0[i_dday] + dtfrac * (G1[i_dday] - G0[i_dday])
    dx = G1[i_lon] - G0[i_lon]
    if dx > 180.0:
        dx -= 360.0
    elif dx <= -180.0:
        dx += 360.0
    x = G0[i_dday] + dtfrac * dx
    y = G0[i_lat] + dtfrac * (G1[i_lat] - G0[i_lat])
    return t, x, y

good_position_dict = {'gps_sea': good_gps_sea,
                      'gps': good_gps}

# end position message info -------------------------------


#----attitude message info------------------------------

# Gyro -------------------------------------------------
iG_heading = field_dict['hdg'].index('heading')
def good_gyro_heading(G):
    h = float(G[iG_heading])
    if h <= 360.0 and h >= 0.0:
        return 1
    return 0

# Seapath ----------------------------------------------
iS_heading = field_dict['sea'].index('heading')
iS_head_qual = field_dict['sea'].index('head_qual')
iS_rp_qual = field_dict['sea'].index('rp_qual')
iS_dday = field_dict['sea'].index('dday')

def good_seapath_attitude(S):
    if int(S[iS_head_qual]) <= 1 and S[iS_rp_qual] == 0.0:
        return 1
    return 0

# Ashtech ----------------------------------------------
iA_heading = field_dict['adu'].index('heading')
iA_reacq = field_dict['adu'].index('reacq')
iS_dday = field_dict['adu'].index('dday')

def good_ashtech_attitude(A):
    if A[iA_reacq] == 0.0:
        return 1
    return 0

# POSMV -------------------------------------------------
iP_dday = field_dict['pmv'].index('dday')
iP_heading = field_dict['pmv'].index('heading')
iP_acc_heading = field_dict['pmv'].index('acc_heading')
iP_flag_GAMS = field_dict['pmv'].index('flag_GAMS')
iP_flag_IMU = field_dict['pmv'].index('flag_IMU')
P_min_GAMS = 1
P_max_acc_heading = 0.5

def good_posmv_attitude(P):
    if (P[iP_flag_IMU] == 0.0 and
        P[iP_flag_GAMS] >= P_min_GAMS and
        P[iP_acc_heading] <= P_max_acc_heading):
        return 1
    return 0

# MAHRS ------------------------------------------------
#    (fields are the same for hnc_tss1 and hdg_tss1)
iT_heading = field_dict['hnc_tss1'].index('heading')
iT_status = field_dict['hnc_tss1'].index('status')

def good_tss_heading(T):
    h = float(T[iT_heading])
    if (int(T[iT_status]) == 7 and
        h <= 360.0 and h >= 0.0):
        return 1
    return 0

good_attitude_dict = {'sea': good_seapath_attitude,
                      'adu': good_ashtech_attitude,
                      'pmv': good_posmv_attitude,
                      'hdg': good_gyro_heading,
                      'hnc': good_gyro_heading,
                      'hdg_tss1' : good_tss_heading,
                      'hnc_tss1' : good_tss_heading}

i_heading_dict = {'sea': iS_heading,
                  'adu': iA_heading,
                  'pmv': iP_heading,
                  'hdg': iG_heading,
                  'hnc': iG_heading,
                  'hdg_tss1' : iT_heading,
                  'hnc_tss1' : iT_heading}

# end attitude message info -------------------------------
