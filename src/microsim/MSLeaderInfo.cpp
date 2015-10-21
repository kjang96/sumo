/****************************************************************************/
/// @file    MSLeaderInfo.cpp
/// @author  Jakob Erdmann
/// @date    Oct 2015
/// @version $Id: MSLeaderInfo.cpp 18663 2015-08-19 13:02:24Z namdre $
///
// Information about vehicles ahead (may be multiple vehicles if
// lateral-resolution is active)
/****************************************************************************/
// SUMO, Simulation of Urban MObility; see http://sumo.dlr.de/
// Copyright (C) 2002-2015 DLR (http://www.dlr.de/) and contributors
/****************************************************************************/
//
//   This file is part of SUMO.
//   SUMO is free software: you can redistribute it and/or modify
//   it under the terms of the GNU General Public License as published by
//   the Free Software Foundation, either version 3 of the License, or
//   (at your option) any later version.
//
/****************************************************************************/


// ===========================================================================
// included modules
// ===========================================================================
#ifdef _MSC_VER
#include <windows_config.h>
#else
#include <config.h>
#endif

#include <cassert>
#include <math.h>
#include <microsim/MSGlobals.h>
#include <microsim/MSVehicle.h>
#include <microsim/MSNet.h>
#include "MSLeaderInfo.h"

#ifdef CHECK_MEMORY_LEAKS
#include <foreign/nvwa/debug_new.h>
#endif // CHECK_MEMORY_LEAKS


// ===========================================================================
// static member variables
// ===========================================================================


// ===========================================================================
// MSLeaderInfo member method definitions
// ===========================================================================
MSLeaderInfo::MSLeaderInfo(SUMOReal width, const MSVehicle* ego) : 
    myWidth(width),
    myVehicles(MAX2(1, int(ceil(width / MSGlobals::gLateralResolution))), (MSVehicle*)0),
    myFreeSublanes((int)myVehicles.size()),
    egoRightMost(-1),
    egoLeftMost(-1),
    myHasVehicles(false)
{ 
    if (ego != 0) {
        getSubLanes(ego, 0, egoRightMost, egoLeftMost);
        // filter out sublanes not of interest to ego
        myFreeSublanes -= egoRightMost;
        myFreeSublanes -= (int)myVehicles.size() - 1 - egoLeftMost;
    }
}


MSLeaderInfo::~MSLeaderInfo() { }


int 
MSLeaderInfo::addLeader(const MSVehicle* veh, bool beyond, SUMOReal latOffset) {
    if (veh == 0) {
        return myFreeSublanes;
    }
    if (myVehicles.size() == 1) {
        // speedup for the simple case
        if (!beyond || myVehicles[0] == 0) {
            myVehicles[0] = veh;
            myFreeSublanes = 0;
            myHasVehicles = true;
        }
        return myFreeSublanes;
    } 
    // map center-line based coordinates into [0, myWidth] coordinates
    int rightmost, leftmost;
    getSubLanes(veh, latOffset, rightmost, leftmost);
    for (int sublane = rightmost; sublane <= leftmost; ++sublane) {
        if ((egoRightMost < 0 || (egoRightMost <= sublane && sublane <= egoLeftMost))
                && (!beyond || myVehicles[sublane] == 0)) {
            myVehicles[sublane] = veh;
            myFreeSublanes--;
            myHasVehicles = true;
        }
    }
    return myFreeSublanes;
}


void 
MSLeaderInfo::clear() {
    myVehicles.assign(myVehicles.size(), (MSVehicle*)0);
    myFreeSublanes = (int)myVehicles.size();
    if (egoRightMost >= 0) {
        myFreeSublanes -= egoRightMost;
        myFreeSublanes -= (int)myVehicles.size() - 1 - egoLeftMost;
    }
}


void 
MSLeaderInfo::getSubLanes(const MSVehicle* veh, SUMOReal latOffset, int& rightmost, int& leftmost) const {
    if (myVehicles.size() == 1) {
        // speedup for the simple case
        rightmost = 0;
        leftmost = 0;
        return;
    }
    // map center-line based coordinates into [0, myWidth] coordinates
    const SUMOReal vehCenter = veh->getLateralPositionOnLane() + 0.5 * myWidth + latOffset;
    const SUMOReal vehHalfWidth = 0.5 * veh->getVehicleType().getWidth();
    const SUMOReal rightVehSide = MAX2((SUMOReal)0,  vehCenter - vehHalfWidth);
    const SUMOReal leftVehSide = MIN2(myWidth, vehCenter + vehHalfWidth);
    rightmost = (int)floor((rightVehSide + NUMERICAL_EPS) / MSGlobals::gLateralResolution);
    leftmost = MIN2((int)myVehicles.size() - 1,(int)floor(leftVehSide / MSGlobals::gLateralResolution));
    //if (veh->getID() == "car2") std::cout << SIMTIME << " veh=" << veh->getID()
    //    << std::setprecision(10)
    //    << " posLat=" << veh->getLateralPositionOnLane()
    //    << " rightVehSide=" << rightVehSide
    //    << " leftVehSide=" << leftVehSide
    //    << " rightmost=" << rightmost
    //    << " leftmost=" << leftmost
    //    << std::setprecision(2)
    //    << "\n";
}


const MSVehicle*
MSLeaderInfo::operator[](int sublane) const {
    assert(sublane >= 0);
    assert(sublane < myVehicles.size());
    return myVehicles[sublane];
}


std::string
MSLeaderInfo::toString() const {
    std::ostringstream oss;
    oss.setf(std::ios::fixed , std::ios::floatfield);
    oss << std::setprecision(2);
    for (int i = 0; i < (int)myVehicles.size(); ++i) {
        oss << Named::getIDSecure(myVehicles[i]);
        if (i < (int)myVehicles.size() - 1) {
            oss << ", ";
        }
    }
    return oss.str();
}


bool
MSLeaderInfo::hasStoppedVehicle() const {
    if (!myHasVehicles) {
        return false;
    }
    for (int i = 0; i < (int)myVehicles.size(); ++i) {
        if (myVehicles[0] != 0 && myVehicles[0]->isStopped()) {
            return true;
        }
    }
    return false;
}

// ===========================================================================
// MSLeaderDistanceInfo member method definitions
// ===========================================================================


MSLeaderDistanceInfo::MSLeaderDistanceInfo(SUMOReal width, const MSVehicle* ego, bool recordLeaders) : 
    MSLeaderInfo(width, ego),
    myRecordLeaders(recordLeaders),
    myDistances(myVehicles.size(), std::numeric_limits<SUMOReal>::max())
{ }


MSLeaderDistanceInfo::~MSLeaderDistanceInfo() { }


int 
MSLeaderDistanceInfo::addLeader(const MSVehicle* veh, SUMOReal dist, SUMOReal latOffset, int sublane) {
    //if (SIMTIME == 31 && gDebugFlag1 && veh != 0 && veh->getID() == "cars.8") {
    //    std::cout << " BREAKPOINT\n";
    //}
    if (veh == 0) {
        return myFreeSublanes;
    }
    dist = myRecordLeaders 
        ? dist + veh->getBackPositionOnLane()
        : dist - (veh->getPositionOnLane() + veh->getVehicleType().getMinGap());
    if (myVehicles.size() == 1) {
        // speedup for the simple case
        if (dist < myDistances[0]) {
            myVehicles[0] = veh;
            myDistances[0] = dist;
            myFreeSublanes = 0;
            myHasVehicles = true;
        }
        return myFreeSublanes;
    } else if (sublane >= 0) {
        // sublane is already given
        if (dist < myDistances[sublane]) {
            myVehicles[sublane] = veh;
            myDistances[sublane] = dist;
            myFreeSublanes--;
            myHasVehicles = true;
        }
        return myFreeSublanes;
    }
    int rightmost, leftmost;
    getSubLanes(veh, latOffset, rightmost, leftmost);
    for (int sublane = rightmost; sublane <= leftmost; ++sublane) {
        if ((egoRightMost < 0 || (egoRightMost <= sublane && sublane <= egoLeftMost))
                && dist < myDistances[sublane]) {
            myVehicles[sublane] = veh;
            myDistances[sublane] = dist;
            myFreeSublanes--;
            myHasVehicles = true;
        }
    }
    return myFreeSublanes;
}


void 
MSLeaderDistanceInfo::clear() {
    MSLeaderInfo::clear();
    myDistances.assign(myVehicles.size(), std::numeric_limits<SUMOReal>::max());
}


CLeaderDist
MSLeaderDistanceInfo::operator[](int sublane) const {
    assert(sublane >= 0);
    assert(sublane < myVehicles.size());
    return std::make_pair(myVehicles[sublane], myDistances[sublane]);
}


std::string
MSLeaderDistanceInfo::toString() const {
    std::ostringstream oss;
    oss.setf(std::ios::fixed , std::ios::floatfield);
    oss << std::setprecision(2);
    for (int i = 0; i < (int)myVehicles.size(); ++i) {
        oss << Named::getIDSecure(myVehicles[i]) << ":";
        if (myVehicles[i] == 0) {
            oss << "inf";
        } else {
            oss << myDistances[i];
        }
        if (i < (int)myVehicles.size() - 1) {
            oss << ", ";
        }
    }
    return oss.str();
}

/****************************************************************************/

