package ch.unibnf.mcs.sparklisa.receiver

import akka.actor.Actor
import ch.unibnf.mcs.sparklisa.topology.NodeType
import org.apache.spark.streaming.receiver.ActorHelper

import scala.io.Source
import scala.util.Random

class SensorSimulatorActorReceiverEval(node: NodeType) extends Actor with ActorHelper {

  private final val sensorNode: NodeType = node

  private final val random = new Random()

  val FILE_NAME = "/node_values_4.txt"

  var values: Array[Double] = Array[Double]();

  private var count: Int = 0

  override def preStart = init()

  case class SensorSimulator()


  def receive = {
    case _: SensorSimulator => pushNodeBlocks()
  }

  def pushNodeBlocks() = {
    while(count < 100) {
      store[(String, Double)]((sensorNode.getNodeId + "_" + count.toString, random.nextGaussian()))
      this.count += 1
      Thread.sleep(2000L)
    }
    self ! SensorSimulator()
  }

  private def init() = {
    Thread.sleep(500L);
//    val pos: Int = Integer.parseInt(sensorNode.getNodeId.replace("node", "")) - 1
//    val text = Source.fromInputStream(getClass().getResourceAsStream(FILE_NAME)).mkString
//    readValues(text, pos)
    self ! SensorSimulator()
  }

//  private def readValues(text: String, pos: Int) {
//    val textArr = text.split("\n")
//    val doubleStrings = textArr.map { l =>
//      l.split(";")(pos)
//    }
//    val doubleValues = doubleStrings.map { s => s.toDouble}
//    values = doubleValues
//  }

}