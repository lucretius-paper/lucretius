package lucretius;

import static java.util.stream.Collectors.joining;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.stream.IntStream;
import java.util.stream.Collectors;


/**
 * Data collector that produces both a runtime {@code Summary} and a online collection of
 * {@Samples}.
 */
public final class PowercapSampleCollector implements SampleCollector{
  /** Loads the data from the baseline and computes the mean runtime after {@code warmUp}. */
  // TODO: this doesn't report a missing baseline verbosely. should we fail if it's missing?
  public static double getBaselineRuntime(int warmUp) {
    // TODO: this is a little hacky; we should see if there's a better way to access the
    // baseline
    String baselinePath = String.join("/", System.getProperty("lucretius.baseline.path"));
    if (baselinePath == null) {
      return 0;
    }
    try {
      // TODO: for now, we only care about the overhead. we may want a verbose "metric"
      BufferedReader reader =
          new BufferedReader(new FileReader(String.join("/", baselinePath, "summary.csv")));
      return reader
          .lines()
          .skip(1 + warmUp)
          .mapToDouble(s -> Summary.parseSummary(s).duration)
          .average()
          .orElse(0);
    } catch (Exception e) {
      return 0;
    }
  }

  private final ArrayList<Summary> summary = new ArrayList<>();
  private final ArrayList<Sample> samples = new ArrayList<>();
  private final ExecutorService executor;

  private volatile boolean isRunning = false;
  private Future<ArrayList<Sample>> sampleFuture;

  private Sample summaryStart;
  private int iteration = 1;

  public PowercapSampleCollector() {
    executor = Executors.newSingleThreadExecutor();
  }

  /**
   * Collects start data for a {@code Summary} and starts collecting {@code Samples} concurrently.
   */
  public void start() {
    isRunning = true;

    // TODO: it's possible we can wrap the data collection into a {@link Supplier}
    summaryStart = new Sample(iteration, getMonotonicTimestamp(), getEnergy());
    sampleFuture =
        executor.submit(
            () -> {
              ArrayList<Sample> samples = new ArrayList<>();
              while (isRunning) {
                samples.add(new Sample(iteration, getMonotonicTimestamp(), getEnergy()));
                try {
                  Thread.sleep(1);
                } catch (Exception e) {
                  System.out.println("couldn't sleep!");
                  e.printStackTrace();
                }
              }

              return samples;
            });
  }

  /** Collects end data for a {@code Summary} and stops collecting {@code Samples} concurrently. */
  public void stop() {
    isRunning = false;

    summary.add(
        new Summary(
            iteration,
            summaryStart.timestamp,
            getMonotonicTimestamp() - summaryStart.timestamp,
            computeEnergyDifference(summaryStart.energy, getEnergy())));
    try {
      samples.addAll(sampleFuture.get());
    } catch (Exception e) {
      System.out.println("couldn't get energy data!");
      e.printStackTrace();
    }

    iteration++;
    // summaryStart = null;
  }

  /** Writes the {@link Summary} and {@link Samples} to the underlying directory as csvs without shutting down the Collector. */
  public void write_iter() {
      //Get the finished iteration's samples
      int prev_iter = this.iteration - 1;
      List<Sample> iter_samples = samples.stream().filter(s->s.iteration == prev_iter).collect(Collectors.toList());
    if (iter_samples.isEmpty()) {
      System.out.println("no energy samples collected!");
      return;
    }
    try {
	String filename = "energy_" + prev_iter + ".csv";
	PrintWriter writer =
	    new PrintWriter(
			    new BufferedWriter(
					       new FileWriter(
							      String.join(
									  "/", System.getProperty("lucretius.output.directory"), filename))));
	int componentCount = samples.get(0).energy[0].length * Powercap.SOCKET_COUNT;
	writer.println(
		       String.join(
				   ",",
				   "iteration",
				   "timestamp",
				   IntStream.range(0, componentCount)
				   .mapToObj(i -> String.format("energy_component_%d", i))
				   .collect(joining(","))));
	for (Sample s : iter_samples) {
        String energy =
            Arrays.stream(s.energy)
                .flatMap(e -> Arrays.stream(e).mapToObj(c -> String.format("%f", c)))
                .collect(joining(","));
        writer.println(String.format("%d,%d,%s", s.iteration, s.timestamp, energy));
      }
      writer.close();
    } catch (IOException e) {
      System.out.println("Unable to write Lucretius energy data!");
      e.printStackTrace();
    }
  }

    
  /** Writes the {@link Summary} and {@link Samples} to the underlying directory as csvs. */
  // TODO: do we want a different data type? what happens if we need more data like counters?
  public void dump() {
    executor.shutdown();
    if (samples.isEmpty()) {
      System.out.println("no energy samples collected!");
      return;
    }
    try {
      PrintWriter writer =
          new PrintWriter(
              new BufferedWriter(
                  new FileWriter(
                      String.join(
                          "/", System.getProperty("lucretius.output.directory"), "summary.csv"))));
      writer.println("iteration,timestamp,duration,energy");
      for (Summary s : summary) {
        writer.println(
            String.format("%d,%d,%d,%f", s.iteration, s.timestamp, s.duration, s.energy));
      }
      writer.close();
    } catch (IOException e) {
      System.out.println("Unable to write Lucretius summary data!");
      e.printStackTrace();
    }

  }

  /** {@link dumps} data from the collector and marks it as accepted or rejected. */
  public void dumpWithStatus(boolean accepted) {
    dump();
    dumpStatus(accepted);
  }

  /** Marks the data as accepted or rejected. */
  public void dumpStatus(boolean accepted) {
    try {
      new File(
              String.join(
                  "/",
                  System.getProperty("lucretius.output.directory"),
                  accepted ? "accepted" : "rejected"))
          .createNewFile();
    } catch (IOException e) {
      System.out.println("Unable to write Lucretius status!");
      e.printStackTrace();
    }
  }

  // helper methods to get the data for the dynamic controller
  // TODO: the evaluation should exist within some sort of "metric evaluator"
  public List<Summary> getSummary() {
    return summary;
  }

  public List<Sample> getSamples() {
    return samples;
  }

  // TODO(timur): this is a poor practice; we should use something like a builder.
  static class Summary {
    final int iteration;
    final long timestamp;
    final long duration;
    final double energy;

    private Summary(int iteration, long timestamp, double energy) {
      this.iteration = iteration;
      this.timestamp = timestamp;
      this.duration = 0;
      this.energy = energy;
    }

    private Summary(int iteration, long timestamp, long duration, double energy) {
      this.iteration = iteration;
      this.timestamp = timestamp;
      this.duration = duration;
      this.energy = energy;
    }

    private static Summary parseSummary(String summaryString) {
      String[] summaryValues = summaryString.split(",");
      return new Summary(
          Integer.parseInt(summaryValues[0]),
          Long.parseLong(summaryValues[1]),
          Long.parseLong(summaryValues[2]),
          Double.parseDouble(summaryValues[3]));
    }
  }

  static class Sample {
    final int iteration;
    final long timestamp;
    final double[][] energy;

    private Sample(int iteration, long timestamp, double[][] energy) {
      this.iteration = iteration;
      this.timestamp = timestamp;
      this.energy = energy;
    }

    @Override
    public String toString() {
      return String.format(
          "%d,%d,%s",
          iteration, timestamp, Arrays.stream(energy).map(Arrays::toString).collect(joining(",")));
    }
  }

  // helpers methods that grab/handle data
  private static long getMonotonicTimestamp() {
    return MonotonicTimestamp.getInstance(
            String.join("/", System.getProperty("lucretius.library.path"), "libMonotonic.so"))
        .getMonotonicTimestamp();
  }

  private static double[][] getEnergy() {
    return Powercap.getEnergyStats();
  }

  private static double computeEnergyDifference(double[][] first, double[][] second) {
    double energy = 0;
    for (int socket = 0; socket < Powercap.SOCKET_COUNT; socket++) {
      for (int component = 0; component < first[socket].length; component++) {
        double diff = second[socket][component] - first[socket][component];
        energy += diff;
      }
    }
    return energy;
  }
}
