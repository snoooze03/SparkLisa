package ch.unibnf.mcs.sparklisa.app

import akka.actor.Props
import ch.unibnf.mcs.sparklisa.TopologyHelper
import ch.unibnf.mcs.sparklisa.listener.TriggeringStreamingListener
import ch.unibnf.mcs.sparklisa.receiver.TriggerableTopologySimulatorActorReceiver
import ch.unibnf.mcs.sparklisa.topology.{NodeType, Topology}
import org.apache.log4j.{Level, Logger}
import org.apache.spark.SparkConf
import org.apache.spark.streaming.dstream.DStream
import org.apache.spark.streaming.{Seconds, StreamingContext}

import scala.collection.JavaConversions._
import scala.collection.JavaConverters._
import scala.collection.mutable

/**
 * Calculates spatial LISA statistics for sent node values, and stores input and results to HDFS.
 * A triggered Receiver is used (i.e. new values are only produces once the previous batch is completely processed)
 */
@Deprecated
object SpatialLisaAppTriggered extends LisaDStreamFunctions with LisaAppConfiguration{

//  val Master: String = "spark://saight02:7077"
      val Master: String = "local[2]"

  def main(args: Array[String]) {
    Logger.getRootLogger.setLevel(Level.INFO)
    initConfig()

    val batchDuration: Int = args(0).toInt
    val rate: Double = args(1).toDouble
    val numBaseStations: Int = args(2).toInt
    val timeout: Int = args(3).toInt
    val topologyPath: String = args(4)

    import org.apache.spark.streaming.StreamingContext._
    val conf: SparkConf = createSparkConf()
    conf.set("spark.default.parallelism", s"$numBaseStations")

    val ssc: StreamingContext = new StreamingContext(conf, Seconds(batchDuration))
    ssc.addStreamingListener(new TriggeringStreamingListener())

    ssc.checkpoint(".checkpoint")

    val topology: Topology = TopologyHelper.topologyFromBareFile(topologyPath, numBaseStations)

    val tempMap: mutable.Map[Integer, NodeType] = TopologyHelper.createNumericalNodeMap(topology).asScala

    // Conversion from java.lang.Integer to scala.Int
    val nodeMap: mutable.Map[Int, NodeType] = for ((k,v) <- tempMap; (nk,nv) = (k.intValue, v)) yield (nk,nv)
    val allValues: DStream[(Int, Double)] = createAllValues(ssc, topology, numBaseStations, rate)

    val runningCount = allValues.count()
    val runningMean = allValues.map(t => (t._2, 1.0)).reduce((a, b) => (a._1 + b._1, a._2 + b._2)).map(t => t._1 / t._2)
    val stdDev = createStandardDev(allValues, runningCount, runningMean)

    // get simulated input values DStream
    val allStandardisedValues = createStandardisedValues(allValues, runningMean, stdDev)
    val allNeighbourValues: DStream[(Int, Double)] = allStandardisedValues.flatMap(t => mapToNeighbourKeys(t, nodeMap))

    // groupByKey yields, for each node key, all neighbours' values
    val neighboursNormalizedSums = allNeighbourValues.groupByKey().mapValues(l => l.sum / l.size.toDouble)
    val finalLisaValues = allStandardisedValues.join(neighboursNormalizedSums).mapValues(d => d._1 * d._2)
    val numberOfBaseStations = topology.getBasestation.size().toString
    val numberOfNodes = topology.getNode.size().toString
    allValues.count().saveAsTextFiles(HdfsPath + s"/results/${numberOfBaseStations}_$numberOfNodes/allValues")
    finalLisaValues.count().saveAsTextFiles(HdfsPath + s"/results/${numberOfBaseStations}_$numberOfNodes/finalCount")

    ssc.start()
    ssc.awaitTermination(timeout*1000)

  }

  private def createAllValues(ssc: StreamingContext, topology: Topology, numBaseStations: Int, rate: Double): DStream[(Int, Double)] = {
    val values: DStream[(Int, Double)] =  ssc.actorStream[(Int, Double)](Props(classOf[TriggerableTopologySimulatorActorReceiver], topology.getNode.toList, rate), "receiver")
    values.repartition(numBaseStations)
    return values
  }
}
