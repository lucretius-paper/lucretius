package lucretius;

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
	Lucretius.connect("my-fibonacci");
	int n = Integer.parseInt(args[0]);
	int iterations = Integer.parseInt(args[1]);
	double[] data = new double[iterations];
	System.out.println(String.format("running fib(%d) %d times", n, iterations));
	SampleCollector collector = new RaplSampleCollector();
	int i = 0;
	while(Lucretius.startRequest()){	    
	    Instant start = Instant.now();
	    collector.start();
	    fib(n);
	    collector.stop();
	    collector.write_iter();
	    Lucretius.finishedNotification();
	    data[i] = Duration.between(start, Instant.now()).toMillis();
	    String message = String.format("computed fib(%d) in %4.0f millis", n, data[i]);
	    System.out.print(message);
	    System.out.print(
			     IntStream.range(0, message.length()).mapToObj(unused -> "\b").collect(joining("")));
	    i++;
	}
	Lucretius.finishedNotification();
	System.out.println();
	double average = Arrays.stream(data).average().getAsDouble();
	double deviation =
	    Math.sqrt(
		      Arrays.stream(data).map(elapsed -> elapsed - average).map(x -> x * x).sum()
		      / data.length);
	System.out.println(
			   String.format("ran fib(%d) in %4.0f +/- %4.4f millis", n, average, deviation));
	collector.dump();
    }
}
