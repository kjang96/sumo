import sumolib.net.generator.cross as netGenerator
import sumolib.net.generator.demand as demandGenerator
from sumolib.net.generator.network import *
from scenarios import * 
import random, math, tempfile


RWS="""
1;0.5104;0.5828;0.5772;0.6332;0.748;2.8719;1.7177
2;0.3432;0.3078;0.3675;0.336;0.4566;1.9838;1.0125
3;0.2107;0.2523;0.2086;0.2895;0.2517;1.3241;0.8154
4;0.3703;0.1997;0.3053;0.2064;0.3579;0.9965;0.4875
5;0.9379;0.4054;0.5936;0.457;0.6685;0.6633;0.6375
6;2.5954;1.3955;1.9009;1.5343;2.2885;0.9947;1.2423
7;6.6675;2.9516;4.9363;3.5946;5.1519;1.0119;1.5891
8;8.9356;5.3546;7.2095;4.5774;7.6271;1.4289;2.7169
9;8.1931;6.0357;6.9139;5.2376;6.8091;2.4236;3.8612
10;6.3549;4.9486;6.0444;4.9067;5.7137;3.9569;5.7839
11;5.496;4.4953;5.3436;5.5661;5.2829;5.4762;6.406
12;5.0961;4.778;5.0059;5.955;5.2941;5.9344;7.0014
13;5.3599;5.2839;5.4039;6.853;5.9041;6.4891;7.3738
14;5.6462;5.9352;5.7807;7.2908;6.4795;7.2301;7.6242
15;5.7565;6.6796;6.1341;8.336;6.8031;7.8309;7.7892
16;6.0419;7.4557;7.0506;9.0655;7.0955;7.4463;7.3836
17;6.9183;9.3616;7.8898;8.6483;6.7089;7.7562;6.9353
18;6.6566;10.19;7.5263;7.7115;6.4494;8.2159;6.7839
19;5.8434;8.5196;6.9226;6.4153;5.942;7.5234;6.331
20;4.4669;5.8307;4.9389;4.2742;4.4143;6.1206;4.9072
21;3.3168;3.8433;3.4602;2.8543;3.5677;4.778;4.0775
22;2.0562;2.3324;2.6526;2.2575;2.7751;3.6782;2.9477
23;1.4711;1.9216;1.7354;1.8819;1.8463;2.3371;2.5049
24;0.7552;0.9392;1.0983;1.118;1.3643;1.5282;2.0705
"""

def getRWScurves():
  RWScurves = [[], [], []]
  for l in RWS.split("\n"):
    l = l.strip().split(";")
    if len(l)<2:
      continue
    RWScurves[0].append(float(l[1]))
    RWScurves[1].append(float(l[2]))
    RWScurves[2].append(float(l[3]))
  return RWScurves

def merge(defaultParams, setParams):
  ret = {}
  for p in defaultParams:
    ret[p] = defaultParams[p]
    if p in setParams:
      ret[p] = setParams[p]
  return ret

class ScenarioSet:
  def __init__(self, name, params):
    self.name = name
    self.params = params
  def getNumRuns(self):
    raise "virtual ScenarioSet/getNumRuns"
  def getAverageDuration(self):
    raise "virtual ScenarioSet/getAverageDuration"
  def iterate(self):
    raise "virtual ScenarioSet/iterate"
  def getRunsMatrix(self):
    raise "virtual ScenarioSet/getRunsMatrix"
  def getInt(self, name):
    return int(self.params[name])
  def getFloat(self, name):
    return float(self.params[name])
  def addTLSParameterFromFile(self, tlsProg, paramFile):
    if paramFile==None: return
    fd = open(paramFile)
    for l in fd.readlines():
      l = l.strip()
      if len(l)==0:
        continue
      v = l.split(":")
      tlsProg.addParameter(v[0], v[1])
    fd.close()
  def adaptOutputs(self, sID, scenario, options, tls_algorithm):
    args = []
    files = {}
    # those set on the command line  
    tripinfoFile = scenario.fullPath('tripinfos_%s.xml' % sID)
    args.extend(['--tripinfo-output', tripinfoFile, '--device.emissions.probability', '1'])
    files["tripinfo"] = [tripinfoFile]
    # those generated using an additional file
    scenario.addAdditionalFile(scenario.fullPath("measures_%s" % sID))
    fdo = open(scenario.fullPath("measures_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    files["trafficLane"] = [scenario.fullPath('traffic_%s.xml' % sID)]
    fdo.write('  <laneData id="traffic" file="%s" freq="60"/>\n' % files["trafficLane"][0])
    files["emissionsLane"] = [scenario.fullPath('emissions_%s.xml' % sID)]
    fdo.write('  <laneData id="traffic" type="emissions" file="%s" freq="60"/>\n' % files["emissionsLane"][0])
    net = sumolib.net.readNet(scenario.NET_FILE, withPrograms=True, withConnections=True)
    seenLanes = set()
    files["tlsstates"] = [scenario.fullPath("tls_states_%s.xml" % (sID))]
    files["coupledE2"] = [scenario.fullPath("coupledE2_%s.xml" % (sID))]
    #files["e2"] = [scenario.fullPath("e2_%s.xml" % (sID))]
    for tlsID in net._id2tls:
      atlsID = tlsID.replace("/", "_")
      tls = net._id2tls[tlsID]
      fdo.write('  <timedEvent type="SaveTLSStates" source="%s" dest="%s"/>\n' % (tlsID, files["tlsstates"][0]))
      for conn in tls._connections:
        laneID = conn[0].getID()
        if laneID in seenLanes:
          continue
        seenLanes.add(laneID)
        fdo.write('  <e2Detector id="%s_%s" lane="%s" pos="-.1" length="200" tl="%s" file="%s" friendlyPos="t"/>\n' % (tlsID, laneID, laneID, tlsID, files["coupledE2"][0]))
      fdo.write('\n')
    #for l in seenLanes:
#      fdo.write('  <e2Detector id="%s" lane="%s" pos="-.1" length="200" file="%s" freq="1" friendlyPos="t"/>\n' % (l, l, files["e2"][0]))
    fdo.write('\n')
    fdo.write("</additional>\n")
    fdo.close()
    return args, files

#--------------------------------------

class ScenarioSet_IterateFlowsNA(ScenarioSet):
  def __init__(self, params):
    ScenarioSet.__init__(self, "iterateFlowsNA", merge(
      {"f1from":"0", "f1to":"2400", "f1step":"400","f2from":"0", "f2to":"2400", "f2step":"400"},
      params))
  def getNumRuns(self):
    f1num = 1 + (self.getInt("f1to") - self.getInt("f1from")) / self.getInt("f1step")
    f2num = 1 + (self.getInt("f2to") - self.getInt("f2from")) / self.getInt("f2step")
    return f1num * f2num
  
  """
  Yields returning a built scenario and its description as key/value pairs
  """
  def iterateScenarios(self):
    desc = {"name":"iterateFlowsNA"}
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
        for f2 in range(self.getInt("f2from"), self.getInt("f2to"), self.getInt("f2step")):
            if f1==0 and f2==0:
              continue
            print "Computing for %s<->%s" % (f1, f2)
            sID = "iterateFlowsNA(%s-%s)" % (f1, f2)
            s = getScenario("BasicCross", {}, False)
            s.demandName = s.fullPath("routes_%s.rou.xml" % sID)
            if fileNeedsRebuild(s.demandName, "duarouter"):
              s.demand = demandGenerator.Demand()
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f1, "2/1_to_1/1", "1/1_to_0/1", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f1, "0/1_to_1/1", "1/1_to_2/1", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f2, "1/2_to_1/1", "1/1_to_1/0", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f2, "1/0_to_1/1", "1/1_to_1/2", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.build(0, 3600, s.netName, s.demandName)
            desc = {"scenario":"iterateFlowsNA", "f1":str(f1), "f2":str(f2)}
            yield s, desc, sID
  def getRunsMatrix(self):
    ret = []
    ranges = [[], []]
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
      ret.append([])
      ranges[0].append(f1)
      for f2 in range(self.getInt("f2from"), self.getInt("f2to"), self.getInt("f2step")):
        ret[-1].append({"scenario":"iterateFlowsNA", "f1":str(f1), "f2":str(f2)})
        ranges[1].append(f2)
    return (ret, ranges)
  def getAverageDuration(self):
    return -1 # !!!
  def adapt2TLS(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s_%s" % (sID, tls_algorithm)))
    fdo = open(scenario.fullPath("tls_adapted_%s_%s.add.xml" % (sID, tls_algorithm)), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      for prog in tls._programs:
        tls._programs[prog]._type = tls_algorithm
        tls._programs[prog]._id = "adapted"
        self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
        fdo.write(tls._programs[prog].toXML(tlsID))
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def getXLabel(self):
    return "horizontal demand [vehicles/h]"
  def getYLabel(self):
    return "vertical demand [vehicles/h]"
        
#--------------------------------------

class ScenarioSet_IterateFlowsA(ScenarioSet):
  def __init__(self, params):
    ScenarioSet.__init__(self, "iterateFlowsA", merge(
      {"f1from":"0", "f1to":"2400", "f1step":"400","f2from":"0", "f2to":"2400", "f2step":"400"},
      params))
  def getNumRuns(self):
    f1num = 1 + (self.getInt("f1to") - self.getInt("f1from")) / self.getInt("f1step")
    f2num = 1 + (self.getInt("f2to") - self.getInt("f2from")) / self.getInt("f2step")
    return f1num * f2num
  
  """
  Yields returning a built scenario and its description as key/value pairs
  """
  def iterateScenarios(self):
    desc = {"name":"iterateFlowsA"}
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
        for f2 in range(self.getInt("f2from"), self.getInt("f2to"), self.getInt("f2step")):
            if f1==0 and f2==0:
              continue
            print "Computing for %s<->%s" % (f1, f2)
            sID = "iterateFlowsA(%s-%s)" % (f1, f2)
            s = getScenario("BasicCross", {}, False)
            s.demandName = s.fullPath("routes_%s.rou.xml" % sID)
            if fileNeedsRebuild(s.demandName, "duarouter"):
              s.demand = demandGenerator.Demand()
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f1, "2/1_to_1/1", "1/1_to_0/1", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f1, "0/1_to_1/1", "1/1_to_2/1", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f2, "1/2_to_1/1", "1/1_to_1/0", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f2, "1/0_to_1/1", "1/1_to_1/2", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.build(0, 3600, s.netName, s.demandName)
              # !!! the following two lines are a hack to pass the numbers instead of recomputing them 
              s.demand._f1Value = f1
              s.demand._f2Value = f2
            desc = {"scenario":"iterateFlowsA", "f1":str(f1), "f2":str(f2)}
            yield s, desc, sID
  def getRunsMatrix(self):
    ret = []
    ranges = [[], []]
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
      ret.append([])
      ranges[0].append(f1)
      for f2 in range(self.getInt("f2from"), self.getInt("f2to"), self.getInt("f2step")):
        ret[-1].append({"scenario":"iterateFlowsA", "f1":str(f1), "f2":str(f2)})
        ranges[1].append(f2)
    return (ret, ranges)
  def getAverageDuration(self):
    return -1 # !!!
  def adapt2TLS(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      for prog in tls._programs:
        tls._programs[prog]._type = tls_algorithm
        tls._programs[prog]._id = "adapted"
        self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
        scenario.demand._f1Value = float(max(scenario.demand._f1Value, 1))
        scenario.demand._f2Value = float(max(scenario.demand._f2Value, 1))
        t = scenario.demand._f1Value + scenario.demand._f2Value
        greens = split_by_proportions(80, (scenario.demand._f1Value/t, scenario.demand._f2Value/t), (10, 10))
        tls._programs[prog]._phases[0][1] = greens[0]
        tls._programs[prog]._phases[3][1] = greens[1]
        fdo.write(tls._programs[prog].toXML(tlsID))
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def getXLabel(self):
    return "horizontal demand [vehicles/h]"
  def getYLabel(self):
    return "vertical demand [vehicles/h]"
        
#--------------------------------------
        
class ScenarioSet_RiLSA1LoadCurves(ScenarioSet):
  def __init__(self, params):
    ScenarioSet.__init__(self, "RiLSA1LoadCurves", merge(
      {},
      params))
  def getNumRuns(self):
    return 3*3*3*3
  """
  Yields returning a built scenario and its description as key/value pairs
  """
  def iterateScenarios(self):
    desc = {"name":"RiLSA1LoadCurves"}
    RWScurves = getRWScurves()
    for iWE,cWE in enumerate(RWScurves):
      for iNS,cNS in enumerate(RWScurves):
        for iEW,cEW in enumerate(RWScurves):
          for iSN,cSN in enumerate(RWScurves):
            yield self.runSingle(RWScurves, iWE, iNS, iEW, iSN)#s, desc, sID
  def runSingle(self, RWScurves, iWE, iNS, iEW, iSN, uID=None):
    cWE = RWScurves[iWE]        
    cNS = RWScurves[iNS]        
    cEW = RWScurves[iEW]        
    cSN = RWScurves[iSN]        
    print "Computing for %s %s %s %s" % (iWE, iNS, iEW, iSN)
    if uID==None:
      sID = "RiLSA1LoadCurves(%s-%s-%s-%s)" % (iWE, iNS, iEW, iSN)
    else:
      sID = "RiLSA1LoadCurves(%s)" % (uID)
    s = getScenario("RiLSA1", {})
    s.demandName = s.fullPath("routes_%s.rou.xml" % sID)
    print s.demandName
    if True:#fileNeedsRebuild(s.demandName, "duarouter"):
      nStreams = []
      for stream in s.demand.streams:
        if stream._departEdgeModel.startswith("nm"):
          nStreams.extend(extrapolateDemand(stream, 3600, cNS, 7).streams)
        elif stream._departEdgeModel.startswith("em"):
          nStreams.extend(extrapolateDemand(stream, 3600, cEW, 7).streams)
        elif stream._departEdgeModel.startswith("sm"):
          nStreams.extend(extrapolateDemand(stream, 3600, cSN, 7).streams)
        elif stream._departEdgeModel.startswith("wm"):
          nStreams.extend(extrapolateDemand(stream, 3600, cWE, 7).streams)
        else:
          print stream._departEdgeModel
          raise "Hmmm, unknown stream??"
      s.demand.streams = nStreams 
      end = 86400
      sampleFactor = None
      seenRatio = None
      if "sample-factor" in self.params:
        sampleFactor = self.params["sample-factor"]
      if "seen-ratio" in self.params:
        seenRatio = self.params["seen-ratio"]
      s.demand.build(0, end, s.netName, s.demandName, sampleFactor, seenRatio)
      desc = {"scenario":"RiLSA1LoadCurves", "iWE":str(iWE), "iNS":str(iNS), "iEW":str(iEW), "iSN":str(iSN)}
      return s, desc, sID
  def getRunsMatrix(self):
    ret = []
    ranges = [[], []]
    RWScurves = getRWScurves()
    i = 0
    for iWE,cWE in enumerate(RWScurves):
      for iNS,cNS in enumerate(RWScurves):
        ret.append([])
        ranges[0].append(i)
        i = i + 1
        j = 0
        for iEW,cEW in enumerate(RWScurves):
          for iSN,cSN in enumerate(RWScurves):
            ret[-1].append({"iWE":str(iWE), "iNS":str(iNS), "iEW":str(iEW), "iSN":str(iSN), "scenario":"RiLSA1LoadCurves"})
            ranges[-1].append(j)
            j = j + 1
    return (ret, ranges)
  def getAverageDuration(self):
    return -1 # !!!        
  def adapt2TLS(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      (streamsNS, streamsWE) = scenario.getOppositeFlows()
      (greens, times) = scenario.buildWAUT(streamsNS, streamsWE)
      for prog in tls._programs:
        i1 = i2 = 0
        for i,p in enumerate(tls._programs[prog]._phases):
          if p[1]==40:
            i1 = i
          elif p[1]==12:
            i2 = i
        for t in greens:
          tls._programs[prog]._type = tls_algorithm
          tls._programs[prog]._id = "adapted" + str(t)
          self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
          tls._programs[prog]._phases[i1][1] = greens[t][1]
          tls._programs[prog]._phases[i2][1] = greens[t][0]
          fdo.write(tls._programs[prog].toXML(tlsID)+"\n")
      fdo.write('\n\t<WAUT startProg="adapted1" refTime="0" id="WAUT_%s">\n' % tlsID)
      for t in times:
        fdo.write('\t\t<wautSwitch to="adapted%s" time="%s"/>\n' % (t[1], t[0]*3600))
      fdo.write("\t</WAUT>\n")
      fdo.write('\n\t<wautJunction junctionID="%s" wautID="WAUT_%s"/>\n' % (tlsID, tlsID)) 
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def adapt2TLS2(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      (streamsNS, streamsWE) = scenario.getOppositeFlows()
      ns = streamsNS[0] / (streamsNS[0]+streamsWE[0])
      we = streamsWE[0] / (streamsNS[0]+streamsWE[0])
      greens = split_by_proportions(72, (ns, we), (10, 10))
      for prog in tls._programs:
        i1 = i2 = 0
        for i,p in enumerate(tls._programs[prog]._phases):
          if p[1]==40:
            i1 = i
          elif p[1]==12:
            i2 = i
        tls._programs[prog]._type = tls_algorithm
        tls._programs[prog]._id = "adapted"
        self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
        
        tls._programs[prog]._phases[i1][1] = greens[1]
        tls._programs[prog]._phases[i2][1] = greens[0]
        fdo.write(tls._programs[prog].toXML(tlsID)+"\n")
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def getXLabel(self):
    return "!!!RWS type"
  def getYLabel(self):
    return "!!!RWS type"
        
#--------------------------------------
        
class ScenarioSet_RiLSA1LoadCurvesOutTLS(ScenarioSet):
  def __init__(self, params):
    ScenarioSet.__init__(self, "RiLSA1LoadCurvesOutTLS", merge(
      {},
      params))
    if "other-green" not in self.params:
      self.params["other-green"] = 31
  def getNumRuns(self):
    return 3*3*3*3
  """
  Yields returning a built scenario and its description as key/value pairs
  """
  def iterateScenarios(self):
    desc = {"name":"RiLSA1LoadCurvesOutTLS"}
    RWScurves = getRWScurves()
    for iWE,cWE in enumerate(RWScurves):
      for iNS,cNS in enumerate(RWScurves):
        for iEW,cEW in enumerate(RWScurves):
          for iSN,cSN in enumerate(RWScurves):
            yield self.getSingle(RWScurves, iWE, iNS, iEW, iSN)#s, desc, sID
  def getSingle(self, RWScurves, iWE, iNS, iEW, iSN, uID=None):
    cWE = RWScurves[iWE]        
    cNS = RWScurves[iNS]        
    cEW = RWScurves[iEW]        
    cSN = RWScurves[iSN]        
    print "Computing for %s %s %s %s" % (iWE, iNS, iEW, iSN)
    if uID==None:
      sID = "RiLSA1LoadCurvesOutTLS(%s-%s-%s-%s)" % (iWE, iNS, iEW, iSN)
    else:
      sID = "RiLSA1LoadCurvesOutTLS(%s)" % (uID)
    s = getScenario("RiLSA1OutTLS", self.params)
    s.demandName = s.fullPath("routes_%s.rou.xml" % sID)
    if True:#fileNeedsRebuild(s.demandName, "duarouter"):
      nStreams = []
      for stream in s.demand.streams:
        if stream._departEdgeModel.startswith("nm"):
          nStreams.extend(extrapolateDemand(stream, 3600, cNS, 7).streams)
        elif stream._departEdgeModel.startswith("em"):
          nStreams.extend(extrapolateDemand(stream, 3600, cEW, 7).streams)
        elif stream._departEdgeModel.startswith("sm"):
          nStreams.extend(extrapolateDemand(stream, 3600, cSN, 7).streams)
        elif stream._departEdgeModel.startswith("wm"):
          nStreams.extend(extrapolateDemand(stream, 3600, cWE, 7).streams)
        else:
          print stream._departEdgeModel
          raise "Hmmm, unknown stream??"
      s.demand.streams = nStreams 
      end = 86400
      sampleFactor = None
      if "sample-factor" in self.params:
        sampleFactor = self.params["sample-factor"]
      s.demand.build(0, end, s.netName, s.demandName, sampleFactor)
      desc = {"scenario":"RiLSA1LoadCurvesOutTLS", "iWE":str(iWE), "iNS":str(iNS), "iEW":str(iEW), "iSN":str(iSN)}
      return s, desc, sID
  def getRunsMatrix(self):
    ret = []
    ranges = [[], []]
    RWScurves = getRWScurves()
    i = 0
    for iWE,cWE in enumerate(RWScurves):
      for iNS,cNS in enumerate(RWScurves):
        ret.append([])
        ranges[0].append(i)
        i = i + 1
        j = 0
        for iEW,cEW in enumerate(RWScurves):
          for iSN,cSN in enumerate(RWScurves):
            ret[-1].append({"iWE":str(iWE), "iNS":str(iNS), "iEW":str(iEW), "iSN":str(iSN), "scenario":"RiLSA1LoadCurves"})
            ranges[-1].append(j)
            j = j + 1
    return (ret, ranges)
  def getAverageDuration(self):
    return -1 # !!!        
  def adapt2TLS(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      (streamsNS, streamsWE) = scenario.getOppositeFlows()
      (greens, times) = scenario.buildWAUT(streamsNS, streamsWE)
      for prog in tls._programs:
        i1 = i2 = 0
        for i,p in enumerate(tls._programs[prog]._phases):
          if p[1]==40:
            i1 = i
          elif p[1]==12:
            i2 = i
        for t in greens:
          tls._programs[prog]._type = tls_algorithm
          tls._programs[prog]._id = "adapted" + str(t)
          self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
          tls._programs[prog]._phases[i1][1] = greens[t][1]
          tls._programs[prog]._phases[i2][1] = greens[t][0]
          fdo.write(tls._programs[prog].toXML(tlsID)+"\n")
      fdo.write('\n\t<WAUT startProg="adapted1" refTime="0" id="WAUT_%s">\n' % tlsID)
      for t in times:
        fdo.write('\t\t<wautSwitch to="adapted%s" time="%s"/>\n' % (t[1], t[0]*3600))
      fdo.write("\t</WAUT>\n")
      fdo.write('\n\t<wautJunction junctionID="%s" wautID="WAUT_%s"/>\n' % (tlsID, tlsID)) 
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def adapt2TLS2(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      if tlsID=="0":
        (streamsNS, streamsWE) = scenario.getOppositeFlows()
        ns = streamsNS[0] / (streamsNS[0]+streamsWE[0])
        we = streamsWE[0] / (streamsNS[0]+streamsWE[0])
        greens = split_by_proportions(72, (ns, we), (10, 10))
        for prog in tls._programs:
          i1 = i2 = 0
          for i,p in enumerate(tls._programs[prog]._phases):
            if p[1]==40:
              i1 = i
            elif p[1]==12:
              i2 = i
          tls._programs[prog]._type = tls_algorithm
          self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
          tls._programs[prog]._phases[i1][1] = greens[1]
          tls._programs[prog]._phases[i2][1] = greens[0]
        tls._programs[prog]._id = "adapted"
        fdo.write(tls._programs[prog].toXML(tlsID)+"\n")
      else:
        tls._programs[prog]._phases[0][1] = self.params["other-green"]
        tls._programs[prog]._id = "adapted"
        fdo.write(tls._programs[prog].toXML(tlsID)+"\n")
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def getXLabel(self):
    return "!!!RWS type"
  def getYLabel(self):
    return "!!!RWS type"
        
#--------------------------------------
        
class ScenarioSet_SinSin(ScenarioSet):
  MEAN = 700.
  AMPLITUDE = 300.

  def __init__(self, params):
    ScenarioSet.__init__(self, "SinSin", merge(
      {"offsetFrom":"0", "offsetTo":"3.14", "offsetStep":".314","freqFrom":"30", "freqTo":"300", "freqStep":"30"},
      params))
    self.offsets = []
    offset = self.getFloat("offsetFrom")
    while offset<self.getFloat("offsetTo"):
      self.offsets.append(offset)
      offset = offset + self.getFloat("offsetStep")
    self.frequencies = []
    frequency = self.getFloat("freqFrom")
    while frequency<self.getFloat("freqTo"):
      self.frequencies.append(frequency)
      frequency = frequency + self.getFloat("freqStep")

  def getNumRuns(self):
    return len(self.offsets)*len(self.frequencies)

  def genDemand(self, scenario, simSteps, offset, frequency):  
    #fd = tempfile.NamedTemporaryFile(mode="w", delete=False)
    fd = open(scenario.demandName, "w")
    #---routes---
    print >> fd, """<routes>
			<route id="WE" edges="0/1_to_1/1 0/1_to_1/1.-100 1/1_to_2/1"/>
			<route id="NS" edges="1/2_to_1/1 1/2_to_1/1.-100 1/1_to_1/0"/>
			<route id="EW" edges="2/1_to_1/1 2/1_to_1/1.-100 1/1_to_0/1"/>
			<route id="SN" edges="1/0_to_1/1 1/0_to_1/1.-100 1/1_to_1/2"/>
    """
    pv1 = 0
    pv2 = 0
    vehNr = 0
    o1 = 0
    o2 = offset
    for i in range(simSteps):
        v = math.sin(o1) * self.AMPLITUDE + self.MEAN
        v = v / 3600.
        pv1 = v + pv1
        if random.uniform(0,1) < pv1:
            pv1 = pv1 - 1.
            print >> fd, '    <vehicle id="%i" type="passenger" route="WE" depart="%i" departSpeed="13.89" />' % (vehNr, i)
            vehNr += 1
            print >> fd, '    <vehicle id="%i" type="passenger" route="EW" depart="%i" departSpeed="13.89" />' % (vehNr, i)
            vehNr += 1
        v = math.sin(o2) * self.AMPLITUDE + self.MEAN
        v = v / 3600.
        pv2 = v + pv2
        if random.uniform(0,1) < pv2:
            pv2 = pv2 - 1.
            print >> fd, '    <vehicle id="%i" type="passenger" route="NS" depart="%i" departSpeed="13.89" />' % (vehNr, i)
            vehNr += 1
            print >> fd, '    <vehicle id="%i" type="passenger" route="SN" depart="%i" departSpeed="13.89" />' % (vehNr, i)
            vehNr += 1
        o1 = o1 + ((math.pi*2)/(frequency*60))
        o2 = o2 + ((math.pi*2)/(frequency*60))

    print >> fd, "</routes>"
    fd.close()  
    #duarouter = sumolib.checkBinary("duarouter")
    #retCode = subprocess.call([duarouter, "-v", "-n", scenario.netName,  "-t", fd.name, "-o", scenario.demandName, "--no-warnings"]) # aeh, implizite no-warnings sind nicht schoen
    #os.remove(fd.name)
  """
  Yields returning a built scenario and its description as key/value pairs
  """
  def iterateScenarios(self):
    desc = {"name":"SinSin"}
    for offset in self.offsets:
        for freq in self.frequencies:
            print "Computing for %s<->%s" % (offset, freq)
            sID = "SinSin(%s-%s)" % (offset, freq)
            s = getScenario("BasicCross", {}, False)
            s.demandName = s.fullPath("routes_%s.rou.xml" % (sID))
            if fileNeedsRebuild(s.demandName, "duarouter"):
              self.genDemand(s, 3600, offset, freq)
            desc = {"scenario":"SinSin", "offset":str(offset), "frequency":str(freq)}
            yield s, desc, sID
  def getRunsMatrix(self):
    ret = []
    ranges = [[], []]
    for offset in self.offsets:
      ret.append([])
      ranges[0].append(offset)
      for freq in self.frequencies:
        ret[-1].append({"scenario":"SinSin", "offset":str(offset), "frequency":str(freq)})
        ranges[1].append(freq)
    return (ret, ranges)
  def getAverageDuration(self):
    return -1 # !!!
  def adapt2TLS(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      for prog in tls._programs:
        tls._programs[prog]._type = tls_algorithm
        tls._programs[prog]._id = "adapted"
        self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
        fdo.write(tls._programs[prog].toXML(tlsID))
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def getXLabel(self):
    return "offset"
  def getYLabel(self):
    return "frequency [s]"
        
#--------------------------------------
        
class ScenarioSet_OneSin(ScenarioSet):
  MAIN_FLOW = 1000.

  def __init__(self, params):
    ScenarioSet.__init__(self, "OneSin", merge(
      {"amplFrom":"0", "amplTo":"1000", "amplStep":"200","freqFrom":"5", "freqTo":"30", "freqStep":"5"},
      params))
    self.amplitudes = []
    amplitude = self.getFloat("amplFrom")
    while amplitude<self.getFloat("amplTo"):
      self.amplitudes.append(amplitude)
      amplitude = amplitude + self.getFloat("amplStep")
    self.frequencies = []
    frequency = self.getFloat("freqFrom")
    while frequency<self.getFloat("freqTo"):
      self.frequencies.append(frequency)
      frequency = frequency + self.getFloat("freqStep")

  def getNumRuns(self):
    return len(self.amplitudes)*len(self.amplitudes)

  def genDemand(self, scenario, simSteps, amplitude, frequency):  
    #fd = tempfile.NamedTemporaryFile(mode="w", delete=False)
    fd = open(scenario.demandName, "w")
    #---routes---
    print >> fd, """<routes>
			<route id="WE" edges="0/1_to_1/1 0/1_to_1/1.-100 1/1_to_2/1"/>
			<route id="NS" edges="1/2_to_1/1 1/2_to_1/1.-100 1/1_to_1/0"/>
			<route id="EW" edges="2/1_to_1/1 2/1_to_1/1.-100 1/1_to_0/1"/>
			<route id="SN" edges="1/0_to_1/1 1/0_to_1/1.-100 1/1_to_1/2"/>
    """
    pv1 = 0
    pv2 = 0
    lastVeh = 0
    vehNr = 0
    o1 = 0
    for i in range(simSteps):
        v = math.sin(o1) * amplitude + 600.
        v = v / 3600.
        pv1 = v + pv1
        if random.uniform(0,1) < pv1:
            pv1 = pv1 - 1.
            print >> fd, '    <vehicle id="%i" type="passenger" route="WE" depart="%i" departSpeed="13.89" />' % (vehNr, i)
            vehNr += 1
            lastVeh = i
            print >> fd, '    <vehicle id="%i" type="passenger" route="EW" depart="%i" departSpeed="13.89" />' % (vehNr, i)
            vehNr += 1
            lastVeh = i	
        o1 = o1 + ((math.pi*2)/(frequency*60))
        pNS = float(self.MAIN_FLOW)/3600
        pSN = float(self.MAIN_FLOW)/3600
        if random.uniform(0,1) < pNS:
            print >> fd, '    <vehicle id="%i" type="passenger" route="NS" depart="%i" departSpeed="13.89" />' % (vehNr, i)
            vehNr += 1
            lastVeh = i
        if random.uniform(0,1) < pSN:
            print >> fd, '    <vehicle id="%i" type="passenger" route="SN" depart="%i" departSpeed="13.89" />' % (vehNr, i)
            vehNr += 1
            lastVeh = i

    print >> fd, "</routes>"
    fd.close()  
    
  """
  Yields returning a built scenario and its description as key/value pairs
  """
  def iterateScenarios(self):
    desc = {"name":"OneSin"}
    for amplitude in self.amplitudes:
        for freq in self.frequencies:
            print "Computing for %s<->%s" % (amplitude, freq)
            sID = "OneSin(%s-%s)" % (amplitude, freq)
            s = getScenario("BasicCross", {}, False)
            s.demandName = s.fullPath("routes_%s.rou.xml" % (sID))
            if fileNeedsRebuild(s.demandName, "duarouter"):
              self.genDemand(s, 3600, amplitude, freq)
            desc = {"scenario":"OneSin", "amplitude":str(amplitude), "frequency":str(freq)}
            yield s, desc, sID
  def getRunsMatrix(self):
    ret = []
    ranges = [[], []]
    for amplitude in self.amplitudes:
      ret.append([])
      ranges[0].append(amplitude)
      for freq in self.frequencies:
        ret[-1].append({"scenario":"OneSin", "amplitude":str(amplitude), "frequency":str(freq)})
        ranges[1].append(freq)
    return (ret, ranges)
  def getAverageDuration(self):
    return -1 # !!!
  def adapt2TLS(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      for prog in tls._programs:
        tls._programs[prog]._type = tls_algorithm
        tls._programs[prog]._id = "adapted"
        self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
        fdo.write(tls._programs[prog].toXML(tlsID))
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def getXLabel(self):
    return "!!!amplitude"
  def getYLabel(self):
    return "frequency [s]"
        
#--------------------------------------
        
class ScenarioSet_DemandStep(ScenarioSet):
  def __init__(self, params):
    ScenarioSet.__init__(self, "DemandStep", merge(
      {"f1from":"0", "f1to":"2400", "f1step":"600",
      "f2beginFrom":"0", "f2beginTo":"2400", "f2beginStep":"600",
      "f2endFrom":"0", "f2endTo":"2400", "f2endStep":"600",
      "f2durationFrom":"0", "f2durationTo":"3601", "f2durationStep":"900",
      },
      params))
  def getNumRuns(self):
    f1num = 1 + (self.getInt("f1to") - self.getInt("f1from")) / self.getInt("f1step")
    f2beginNum = 1 + (self.getInt("f2beginTo") - self.getInt("f2beginFrom")) / self.getInt("f2beginStep")
    f2endNum = 1 + (self.getInt("f2endTo") - self.getInt("f2endFrom")) / self.getInt("f2endStep")
    f2durationNum = 1 + (self.getInt("f2durationTo") - self.getInt("f2durationFrom")) / self.getInt("f2durationStep")
    return f1num * f2beginNum * f2endNum * f2durationNum

  def iterateScenarios(self):
    desc = {"name":"iterateFlowsNA"}
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
      for f2begin in range(self.getInt("f2beginFrom"), self.getInt("f2beginTo"), self.getInt("f2beginStep")):
        for f2end in range(self.getInt("f2endFrom"), self.getInt("f2endTo"), self.getInt("f2endStep")):
          for f2duration in range(self.getInt("f2durationFrom"), self.getInt("f2durationTo"), self.getInt("f2durationStep")):        
            if f1==0 and f2begin==0 and f2end==0:
              continue
            print "Computing for %s<->%s->%s@%s" % (f1, f2begin, f2end, f2duration)
            sID = "DemandStep(%s-%s-%s-%s)" % (f1, f2begin, f2end, f2duration)
            s = getScenario("BasicCross", {}, False)
            s.demandName = s.fullPath("routes_%s.rou.xml" % sID)
            if True:#fileNeedsRebuild(s.demandName, "duarouter"):
              hd = f2duration/2
              s.demand = demandGenerator.Demand()
              s.demand.addStream(demandGenerator.Stream(None, 0, 7200, f1, "2/1_to_1/1", "1/1_to_0/1", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 0, 7200, f1, "0/1_to_1/1", "1/1_to_2/1", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              # begin              
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600-hd, f2begin, "1/2_to_1/1", "1/1_to_1/0", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600-hd, f2begin, "1/0_to_1/1", "1/1_to_1/2", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              # between
              for t in range(0, f2duration, 300):
                fat = (f2end-f2begin) / f2duration * (t+150)
                s.demand.addStream(demandGenerator.Stream(None, 3600-hd+t, 3600-hd+t+300, fat, "1/2_to_1/1", "1/1_to_1/0", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
                s.demand.addStream(demandGenerator.Stream(None, 3600-hd+t, 3600-hd+t+300, fat, "1/0_to_1/1", "1/1_to_1/2", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              # end              
              s.demand.addStream(demandGenerator.Stream(None, 3600+hd, 7200, f2end, "1/2_to_1/1", "1/1_to_1/0", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 3600+hd, 7200, f2end, "1/0_to_1/1", "1/1_to_1/2", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.build(0, 7200, s.netName, s.demandName)
              # !!! the following two lines are a hack to pass the numbers instead of recomputing them 
            s.demand._f1Value = f1
            s.demand._f2Value = (f2begin+f2end)/2.
            desc = {"scenario":"DemandStep", "f1":str(f1), "f2begin":str(f2begin), "f2end":str(f2end), "f2duration":str(f2duration)}
            yield s, desc, sID
  def getRunsMatrix(self):
    ret = []
    ranges = [[], []]
    RWScurves = getRWScurves()
    i = 0
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
      for f2begin in range(self.getInt("f2beginFrom"), self.getInt("f2beginTo"), self.getInt("f2beginStep")):        
        ret.append([])
        ranges[0].append(i)
        i = i + 1
        j = 0
        for f2end in range(self.getInt("f2endFrom"), self.getInt("f2endTo"), self.getInt("f2endStep")):
          for f2duration in range(self.getInt("f2durationFrom"), self.getInt("f2durationTo"), self.getInt("f2durationStep")):        
            ret[-1].append({"f1":str(f1), "f2begin":str(f2begin), "f2end":str(f2end), "f2duration":str(f2duration), "scenario":"DemandStep"})
            ranges[-1].append(j)
            j = j + 1
    return (ret, ranges)
  def getAverageDuration(self):
    return -1 # !!!
  def adapt2TLS(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      for prog in tls._programs:
        tls._programs[prog]._type = tls_algorithm
        tls._programs[prog]._id = "adapted"
        self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
        scenario.demand._f1Value = float(max(scenario.demand._f1Value, 1))
        scenario.demand._f2Value = float(max(scenario.demand._f2Value, 1))
        t = scenario.demand._f1Value + scenario.demand._f2Value
        greens = split_by_proportions(80, (scenario.demand._f1Value/t, scenario.demand._f2Value/t), (10, 10))
        tls._programs[prog]._phases[0][1] = greens[0]
        tls._programs[prog]._phases[3][1] = greens[1]
        fdo.write(tls._programs[prog].toXML(tlsID))
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def getXLabel(self):
    return "!!!"
  def getYLabel(self):
    return "!!!"

#--------------------------------------
        
class ScenarioSet_CorrFlowsDistancesA(ScenarioSet):
  def __init__(self, params):
    ScenarioSet.__init__(self, "CorrFlowsDistancesA", merge(
      {"f1from":"0", "f1to":"2400", "f1step":"400",
      "f2from":"0", "f2to":"2400", "f2step":"400",
      "d1from":"300", "d1to":"1000", "d1step":"100"},
      params))
  def getNumRuns(self):
    f1num = 1 + (self.getInt("f1to") - self.getInt("f1from")) / self.getInt("f1step")
    f2num = 1 + (self.getInt("f2to") - self.getInt("f2from")) / self.getInt("f2step")
    d1num = 1 + (self.getInt("d1to") - self.getInt("d1from")) / self.getInt("d1step")
    return f1num * f2num * d1num
  def iterateScenarios(self):
    desc = {"name":"CorrFlowsDistancesA"}
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
      for f2 in range(self.getInt("f2from"), self.getInt("f2to"), self.getInt("f2step")):
        for d1 in range(self.getInt("d1from"), self.getInt("d1to"), self.getInt("d1step")):
            if f1==0 and f2==0:
              continue
            print "Computing for %s<->%s %s" % (f1, f2, d1)
            sID = "CorrFlowsDistancesA(%s-%s-%s)" % (f1, f2, d1)
            s = getScenario("BasicCorridor", {"xoff":d1}, False)
            s.demandName = s.fullPath("routes_%s.rou.xml" % sID)
            if fileNeedsRebuild(s.demandName, "duarouter"):
              s.demand = demandGenerator.Demand()
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f1, "6/1_to_5/1", "1/1_to_0/1", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f1, "0/1_to_1/1", "5/1_to_6/1", { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              for i in range(1, 6):
                s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f2, "%s/2_to_%s/1" % (i,i), "%s/1_to_%s/0" % (i,i), { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
                s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f2, "%s/0_to_%s/1" % (i,i), "%s/1_to_%s/2" % (i,i), { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.build(0, 3600, s.netName, s.demandName)
              # !!! the following two lines are a hack to pass the numbers instead of recomputing them 
              s.demand._f1Value = f1
              s.demand._f2Value = f2
            desc = {"scenario":"CorrFlowsDistancesA", "f1":str(f1), "f2":str(f2), "d1":str(d1)}
            yield s, desc, sID
  def getRunsMatrix(self):
    ret = []
    ranges = [[], []]
    RWScurves = getRWScurves()
    i = 0
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
      for f2 in range(self.getInt("f2from"), self.getInt("f2to"), self.getInt("f2step")):        
        ret.append([])
        ranges[0].append(i)
        i = i + 1
        j = 0
        for d1 in range(self.getInt("d1from"), self.getInt("d1to"), self.getInt("d1step")):
          ret[-1].append({"f1":str(f1), "f2":str(f2), "d1":str(d1), "scenario":"CorrFlowsDistancesA"})
          ranges[-1].append(j)
          j = j + 1
    return (ret, ranges)
  def getAverageDuration(self):
    return -1 # !!!
  def adapt2TLS(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      for prog in tls._programs:
        tls._programs[prog]._type = tls_algorithm
        tls._programs[prog]._id = "adapted"
        self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
        scenario.demand._f1Value = float(max(scenario.demand._f1Value, 1))
        scenario.demand._f2Value = float(max(scenario.demand._f2Value, 1))
        t = scenario.demand._f1Value + scenario.demand._f2Value
        greens = split_by_proportions(80, (scenario.demand._f1Value/t, scenario.demand._f2Value/t), (10, 10))
        tls._programs[prog]._phases[0][1] = greens[0]
        tls._programs[prog]._phases[3][1] = greens[1]
        fdo.write(tls._programs[prog].toXML(tlsID))
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def getXLabel(self):
    return "!!!"
  def getYLabel(self):
    return "!!!"

#--------------------------------------    
        
class ScenarioSet_NetFlowsDistancesA(ScenarioSet):
  def __init__(self, params):
    ScenarioSet.__init__(self, "NetFlowsDistancesA", merge(
      {"f1from":"0", "f1to":"2400", "f1step":"400",
      "f2from":"0", "f2to":"2400", "f2step":"400",
      "oFrom":"0", "oTo":"3.14", "oStep":".314"},
      params))
  def getNumRuns(self):
    f1num = 1 + (self.getInt("f1to") - self.getInt("f1from")) / self.getInt("f1step")
    f2num = 1 + (self.getInt("f2to") - self.getInt("f2from")) / self.getInt("f2step")
    self.offsets = []
    offset = self.getFloat("oFrom")
    while offset<self.getFloat("oTo"):
      self.offsets.append(offset)
      offset = offset + self.getFloat("oStep")
    return f1num * f2num * len(self.offsets)
  def iterateScenarios(self):
    desc = {"name":"NetFlowsDistancesA"}
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
      for f2 in range(self.getInt("f2from"), self.getInt("f2to"), self.getInt("f2step")):
        for o in self.offsets:
            if f1==0 and f2==0:
              continue
            print "Computing for %s %s<->%s" % (o, f1, f2)
            sID = "NetFlowsDistancesA(%s-%s-%s)" % (f1, f2, o)
            s = getScenario("BasicNet", {"rot":o}, False)
            s.demandName = s.fullPath("routes_%s.rou.xml" % sID)
            if fileNeedsRebuild(s.demandName, "duarouter"):
              s.demand = demandGenerator.Demand()
              for i in range(1, 6):
                s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f1, "6/%s_to_5/%s" % (i,i), "1/%s_to_0/%s" % (i,i), { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
                s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f1, "0/%s_to_1/%s" % (i,i), "5/%s_to_6/%s" % (i,i), { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              for i in range(1, 6):
                s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f2, "%s/6_to_%s/5" % (i,i), "%s/1_to_%s/0" % (i,i), { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
                s.demand.addStream(demandGenerator.Stream(None, 0, 3600, f2, "%s/0_to_%s/1" % (i,i), "%s/5_to_%s/6" % (i,i), { 1:"passenger"})) # why isn't it possible to get a network and return all possible routes or whatever - to ease the process
              s.demand.build(0, 3600, s.netName, s.demandName)
              # !!! the following two lines are a hack to pass the numbers instead of recomputing them 
              s.demand._f1Value = f1
              s.demand._f2Value = f2
            desc = {"scenario":"NetFlowsDistancesA", "f1":str(f1), "f2":str(f2), "o":str(o)}
            yield s, desc, sID
  def getRunsMatrix(self):
    ret = []
    ranges = [[], []]
    for f1 in range(self.getInt("f1from"), self.getInt("f1to"), self.getInt("f1step")):
      for f2 in range(self.getInt("f2from"), self.getInt("f2to"), self.getInt("f2step")):
        ret.append([])
        ranges[0].append(f1)
        for o in self._offsets:
          ret[-1].append({"scenario":"NetFlowsDistancesA", "f1":str(f1), "f2":str(f2), "o":str(o)})
          ranges[1].append(f2)
    return (ret, ranges)
  def getAverageDuration(self):
    return -1 # !!!
  def adapt2TLS(self, sID, scenario, options, tls_algorithm):
    # adapt tls to current settings
    scenario.addAdditionalFile(scenario.fullPath("tls_adapted_%s" % sID))
    fdo = open(scenario.fullPath("tls_adapted_%s.add.xml" % sID), "w")
    fdo.write("<additional>\n")
    net = sumolib.net.readNet(scenario.TLS_FILE, withPrograms=True)
    for tlsID in net._id2tls:
      tls = net._id2tls[tlsID]
      for prog in tls._programs:
        tls._programs[prog]._type = tls_algorithm
        tls._programs[prog]._id = "adapted"
        self.addTLSParameterFromFile(tls._programs[prog], options.tls_params)
        scenario.demand._f1Value = float(max(scenario.demand._f1Value, 1))
        scenario.demand._f2Value = float(max(scenario.demand._f2Value, 1))
        t = scenario.demand._f1Value + scenario.demand._f2Value
        greens = split_by_proportions(80, (scenario.demand._f1Value/t, scenario.demand._f2Value/t), (10, 10))
        tls._programs[prog]._phases[0][1] = greens[0]
        tls._programs[prog]._phases[3][1] = greens[1]
        fdo.write(tls._programs[prog].toXML(tlsID))
    fdo.write("</additional>\n")
    fdo.close()
    scenario.addAdditionalFile("vtypes")
    args = []
    return args
  def getXLabel(self):
    return "horizontal demand [vehicles/h]"
  def getYLabel(self):
    return "vertical demand [vehicles/h]"

#--------------------------------------

def getScenarioSet(name, params):
  if name=="iterateFlowsNA":
    return ScenarioSet_IterateFlowsNA(params)  
  if name=="iterateFlowsA":
    return ScenarioSet_IterateFlowsA(params)  
  if name=="RiLSA1LoadCurves":
    return ScenarioSet_RiLSA1LoadCurves(params)  
  if name=="RiLSA1LoadCurvesOutTLS":
    return ScenarioSet_RiLSA1LoadCurvesOutTLS(params)  
  if name=="SinSin":
    return ScenarioSet_SinSin(params)  
  if name=="OneSin":
    return ScenarioSet_OneSin(params)  
  if name=="DemandStep":
    return ScenarioSet_DemandStep(params)  
  if name=="CorrFlowsDistancesA":
    return ScenarioSet_CorrFlowsDistancesA(params)  
  if name=="NetFlowsA":
    return ScenarioSet_NetFlowsA(params)
  if name=="NetFlowsDistancesA":
    return ScenarioSet_NetFlowsDistancesA(params)
  raise "unknown scenario '%s'" % name

def getAllScenarioSets():
  return ";".join(["iterateFlowsNA", "RiLSA1LoadCurves", "SinSin", "OneSin", "DemandStep"])    