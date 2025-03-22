package vesta;

import org.renaissance.Plugin;

/** {@link Plugin} for renaissance that wraps usage of the {@link SampleCollector}. */
public class VestaRenaissancePlugin
    implements Plugin.BeforeBenchmarkTearDownListener,
        Plugin.AfterOperationSetUpListener,
        Plugin.BeforeOperationTearDownListener {
  private final SampleCollector collector = new SampleCollector();

  @Override
  public void afterOperationSetUp(String benchmark, int opIndex, boolean isLastOp) {
    collector.start();
  }

  @Override
  public void beforeOperationTearDown(String benchmark, int opIndex, long durationNanos) {
    collector.stop();
  }

  @Override
  public void beforeBenchmarkTearDown(String benchmark) {
    System.out.println("dumping data");
    collector.dump();
  }
}
