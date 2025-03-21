package vesta;

import static java.util.stream.Collectors.joining;

import java.time.Duration;
import java.time.Instant;
import java.util.Arrays;
import java.util.stream.IntStream;

final class MyFibonacci {
  private static int fib(int n) {
    if (n == 0 || n == 1) {
      return n;
    } else {
      return fib(n - 1) + fib(n - 2);
    }
  }

  public static void main(String[] args) {
    int n = Integer.parseInt(args[0]);
    int iterations = Integer.parseInt(args[1]);
    double[] data = new double[iterations];

    System.out.println(String.format("running fib(%d) %d times", n, iterations));
    SampleCollector collector = new SampleCollector();
    for (int i = 0; i < iterations; i++) {
      Instant start = Instant.now();
      collector.start();
      fib(n);
      collector.stop();
      data[i] = Duration.between(start, Instant.now()).toMillis();

      String message = String.format("computed fib(%d) in %4.0f millis", n, data[i]);
      System.out.print(message);
      System.out.print(
          IntStream.range(0, message.length()).mapToObj(unused -> "\b").collect(joining("")));
    }
    System.out.println();
    double average = Arrays.stream(data).average().getAsDouble();
    double deviation =
        Math.sqrt(
            Arrays.stream(data).map(elapsed -> elapsed - average).map(i -> i * i).sum()
                / data.length);
    System.out.println(
        String.format("ran fib(%d) in %4.0f +/- %4.4f millis", n, average, deviation));
    collector.dump();
  }
}
