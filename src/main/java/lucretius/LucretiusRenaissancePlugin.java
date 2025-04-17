package lucretius;

import org.renaissance.Plugin;

/** {@link Plugin} for renaissance that wraps usage of the {@link SampleCollector}. */
public class LucretiusRenaissancePlugin
    implements Plugin.BeforeBenchmarkTearDownListener,
        Plugin.AfterOperationSetUpListener,
	Plugin.BeforeOperationTearDownListener,
	Plugin.ExecutionPolicy,
	Plugin.BeforeBenchmarkSetUpListener{
  private SampleCollector collector;

  @Override
  public void beforeBenchmarkSetUp(String benchmark){
      if(System.getProperty("lucretius.use.jrapl") != null){
	  collector = new RaplSampleCollector();
      }else{
	  collector = new PowercapSampleCollector();
      }
      boolean response = Lucretius.connect(benchmark);
      System.out.println("CONNECTED? "+response);
  }
    
  @Override
  public void afterOperationSetUp(String benchmark, int opIndex, boolean isLastOp) {
    collector.start();
  }

  @Override
  public void beforeOperationTearDown(String benchmark, int opIndex, long durationNanos) {
    collector.stop();
    collector.write_iter();
    Lucretius.finishedNotification();
  }

  @Override
  public void beforeBenchmarkTearDown(String benchmark) {
    System.out.println("dumping data");
    collector.dump();
    Lucretius.finishedNotification();
  }

  @Override
  public boolean canExecute(String benchmark, int opIndex){
      boolean response = Lucretius.startRequest();
      System.out.println("CAN RUN? " + response);
      return response;
  }

  @Override
  public boolean isLast(String benchmark, int opIndex){
      return false;
  }
}
