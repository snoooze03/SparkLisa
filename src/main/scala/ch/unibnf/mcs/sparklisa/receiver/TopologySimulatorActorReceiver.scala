package ch.unibnf.mcs.sparklisa.receiver

import akka.actor.{ActorSystem, UntypedActor, Actor}
import ch.unibnf.mcs.sparklisa.topology.{NodeType, Topology}
import org.apache.spark.streaming.receiver.ActorHelper

import scala.collection.JavaConversions._
import scala.collection.mutable
import scala.concurrent.duration._
import scala.util.Random
import scala.concurrent.ExecutionContext.Implicits.global

class TopologySimulatorActorReceiver(nodes: List[NodeType], rate: Int) extends Actor with ActorHelper {

  val random = new Random()
  private val sleepDuration: Int = ((rate / 60.0) * 1000).toInt

  override def preStart = {
    context.system.scheduler.schedule((sleepDuration * 3.5) milliseconds, sleepDuration milliseconds)({
      val values: mutable.MutableList[(String, Double)] = mutable.MutableList()
      for (node <- nodes) {
        values += ((node.getNodeId, random.nextGaussian()))
      }
      self ! values.iterator
    })
  }

  case class SensorSimulator()

  override def receive = {
    case data: Iterator[(String, Double)] => {
      store[(String, Double)](data)
    }
  }
}