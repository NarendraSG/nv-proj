import { APIGatewayProxyEvent, APIGatewayProxyResult } from "aws-lambda";
import { PrismaClient } from "./prisma";
import { ConnectionIsNotSetError } from "typeorm";

const prisma = new PrismaClient();

console.log("HELLO_WORLD");




export const lambdaHandlerfgfd = async (
  event?: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  logger("HELLO_WORLD");
  let response: APIGatewayProxyResult; // this is fiigsdfds

  console.log("HELLO_WORLD");
  try {
    let a = 10;
    let b = 20;
    const user = await prisma.user.create({
      data: {
        name: "Alice",
        email: "alice@prisma.io123",
      },
    });

    response = {
      statusCode: 200,
      body: JSON.stringify({
        message: `hello world from function1 qwerty`,
      }),
    };
  } catch (err: unknown) {
    console.error(err);
    response = {
      statusCode: 500,
      body: JSON.stringify({
        message: err instanceof Error ? err.message : "some error happened",
      }),
    };
  }

  console.log("HELLO_WORLD");
  console.log(response);
  console.log("HELLO_WORLD1");
 
  return response;

};
