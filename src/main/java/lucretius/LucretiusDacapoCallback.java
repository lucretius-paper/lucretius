package lucretius;

import org.dacapo.harness.Callback;
import org.dacapo.harness.CommandLineArgs;
import org.dacapo.parser.Config;

/** {@link Callback} for dacapo that wraps usage of the {@link SampleCollector}. */
public class LucretiusDacapoCallback extends Callback {
  private final SampleCollector collector;

  public LucretiusDacapoCallback(CommandLineArgs args) {
    super(args);
    if(System.getProperty("lucretius.use.jrapl") != null){
	collector = new RaplSampleCollector();
    }else{
	collector = new PowercapSampleCollector();
    }
    
  }

  @Override
  public void start(String benchmark) {
    super.start(benchmark);
    collector.start();
  }

  @Override
  public void stop(long w) {
    super.stop(w);
    collector.stop();
    collector.write_iter();
    Lucretius.finishedNotification();
  }

  @Override
  public boolean runAgain() {
    // if we have run every iteration, dump the data and terminate
    // if (!super.runAgain()) {
    if(!Lucretius.startRequest()){
      System.out.println("dumping data");
      collector.dump();
      Lucretius.finishedNotification();
      return false;
    } else {
      return true;
    }
  }


    @Override
    public void init(Config config){
	//Dacapo runs the benchmark immediately after the init finishes, so we have to wait on the request here
	super.init(config);
	Lucretius.connect(config.name);
	Lucretius.startRequest();
    }
    
}
