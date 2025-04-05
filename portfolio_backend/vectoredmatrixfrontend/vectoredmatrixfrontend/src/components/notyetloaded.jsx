import RingLoader from "react-spinners/RingLoader";

const Notyetloader = () => {
  return (
    <>
      <div className="flex items-center h-96   justify-center ">
        <RingLoader color="#ff8c06" size={200} />
      </div>
    </>
  );
};

export default Notyetloader;
